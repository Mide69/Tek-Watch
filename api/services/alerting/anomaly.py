"""AI anomaly detection engine — uses Claude to detect unusual patterns."""
import asyncio
import json
import logging
from typing import Any, Dict, List

from anthropic import Anthropic

from config import load_config
from services.dynamodb import DynamoDBService
from services.notifications import NotificationService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

ANOMALY_DETECTION_SYSTEM_PROMPT = """You are a cloud infrastructure anomaly detector for Tek Watch, a managed cloud service platform.
You will be given a JSON object containing:
- "baseline": 7-day hourly averages and standard deviations for key metrics per resource
- "recent": metric values from the last 1 hour for the same resources

Analyse the recent values against the baseline and identify genuine anomalies — unusual deviations that could indicate a problem.

Rules:
- Only flag statistically significant anomalies (> 2 standard deviations from mean, or step-change patterns)
- Do not flag normal business-hours traffic patterns
- Do not flag metrics with insufficient baseline data (< 24 hours of history)
- Focus on actionable issues, not noise

Respond ONLY with a valid JSON array. No preamble, no explanation, no markdown. Example format:
[
  {
    "resource_id": "i-0abc123",
    "service": "ec2",
    "severity": "high",
    "description": "CPU utilisation has jumped from a 7-day average of 23% to 91% in the last hour, suggesting an unexpected workload spike or runaway process.",
    "recommendation": "Check running processes on this instance. If no known deployment or batch job is scheduled, investigate for unauthorised activity."
  }
]

If no anomalies are detected, respond with an empty array: []"""


async def detect_anomalies_for_customer(
    customer_id: str,
    ts_service: TimestreamQueryService,
    db_service: DynamoDBService,
    notif_service: NotificationService,
    claude_client: Anthropic,
) -> int:
    """Run anomaly detection for a single customer using Claude.

    Returns:
        Number of new anomaly alerts created.
    """
    # Get 7-day baseline
    baseline = ts_service.get_7day_summary(customer_id)
    if not baseline:
        logger.debug("No baseline data for customer %s", customer_id)
        return 0

    # Get last hour data
    recent = ts_service.get_last_hour(customer_id)
    if not recent:
        logger.debug("No recent data for customer %s", customer_id)
        return 0

    # Build prompt payload
    payload = {
        "customer_id": customer_id,
        "baseline": baseline[:100],  # Limit to avoid token overflow
        "recent": recent[:100],
    }

    try:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=ANOMALY_DETECTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )

        content = response.content[0].text
        anomalies = json.loads(content)

        if not isinstance(anomalies, list):
            logger.warning("Claude returned non-list response for %s", customer_id)
            return 0

    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude response for %s: %s", customer_id, exc)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("Claude API error for %s: %s", customer_id, exc)
        return 0

    # Get existing active AI anomaly alerts
    active_alerts = db_service.get_alerts(customer_id, status_filter="active")
    active_ai_keys = {
        f"{a.get('service')}#{a.get('resource_id')}"
        for a in active_alerts
        if a.get("type") == "ai_anomaly"
    }

    new_alerts = 0

    for anomaly in anomalies:
        resource_id = anomaly.get("resource_id", "")
        service = anomaly.get("service", "")
        severity = anomaly.get("severity", "medium")
        description = anomaly.get("description", "")
        recommendation = anomaly.get("recommendation", "")

        if not resource_id or not service:
            continue

        # Check for duplicate
        alert_key = f"{service}#{resource_id}"
        if alert_key in active_ai_keys:
            continue

        # Create alert
        alert_id = db_service.create_alert(customer_id, {
            "type": "ai_anomaly",
            "severity": severity,
            "service": service,
            "resource_id": resource_id,
            "metric_name": "anomaly",
            "description": description,
            "recommendation": recommendation,
        })

        if alert_id:
            new_alerts += 1
            active_ai_keys.add(alert_key)
            await notif_service.send_ops_alert(
                customer_id=customer_id,
                service=service,
                resource_id=resource_id,
                metric_name="AI Anomaly",
                severity=severity,
                description=description,
            )

    return new_alerts


async def anomaly_detection_loop() -> None:
    """Background task — runs anomaly detection every 15 minutes."""
    config = load_config()
    
    if not config.anthropic_api_key:
        logger.warning("Anthropic API key not configured — anomaly detection disabled")
        return

    claude_client = Anthropic(api_key=config.anthropic_api_key)
    ts_service = TimestreamQueryService()
    db_service = DynamoDBService()
    notif_service = NotificationService()

    logger.info("Anomaly detection loop started (interval: 15 min)")

    while True:
        try:
            customers = db_service.list_customers()
            active = [c for c in customers if c.get("status") == "active"]

            for customer in active:
                await detect_anomalies_for_customer(
                    customer["customer_id"],
                    ts_service,
                    db_service,
                    notif_service,
                    claude_client,
                )

        except Exception as exc:  # noqa: BLE001
            logger.error("Anomaly detection loop error: %s", exc)

        await asyncio.sleep(15 * 60)  # 15 minutes
