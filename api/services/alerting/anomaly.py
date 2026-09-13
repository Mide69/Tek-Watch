"""Anomaly detection loop.

What counts as an anomaly is decided by TekWatch's own statistics in
detector.py: a z-score and a step-change test over every metric's 7-day
baseline. Claude is used for one thing only, and only when a key is
configured: turning the anomalies the detector already found into plain
English. It is told it may not add, remove or re-grade them, and its answer is
discarded unless it returns exactly one explanation per anomaly.

This used to be the other way round. The whole decision was a prompt, the loop
switched itself off entirely when no Anthropic key was set, and it only ever
sent the first 100 rows of each input, so most of a real account's metrics
were never looked at.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from config import load_config
from services.alerting.detector import Anomaly, describe, detect
from services.dynamodb import DynamoDBService
from services.notifications import NotificationService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

EXPLAIN_MODEL = "claude-sonnet-4-20250514"
EXPLAIN_LIMIT = 20          # anomalies explained per call; the rest use built-in wording
INTERVAL_SECONDS = 30 * 60
# How old a stored baseline may be before it is recomputed. A week of
# history barely moves in six hours, and recomputing it is the most
# expensive thing this service does.
BASELINE_MAX_AGE = timedelta(hours=6)
# The first pass reads a week of every metric. Starting it the instant the
# process boots put that load on top of startup, while the load balancer was
# still deciding whether the new task was healthy.
STARTUP_DELAY_SECONDS = 120

EXPLAIN_SYSTEM_PROMPT = """You write short plain-English explanations of cloud monitoring anomalies for UK business owners who are not engineers.

You are given a JSON array of anomalies that have ALREADY been detected by statistical tests. Do not decide whether they are anomalies. Do not add, remove, merge or reorder items, and do not change their severity.

For each item, in the same order, return an object with:
- "description": one or two sentences on what changed, using the numbers given
- "recommendation": one concrete next step

Respond ONLY with a JSON array containing exactly the same number of items. No preamble, no markdown."""


def _dec(value: Optional[float]) -> Optional[Decimal]:
    """DynamoDB rejects Python floats, so every number stored is a Decimal."""
    if value is None:
        return None
    return Decimal(str(round(float(value), 6)))


def _explain_with_claude(client: Any, batch: List[Anomaly]) -> Optional[List[Tuple[str, str]]]:
    payload = [
        {
            "service": a.service,
            "resource_id": a.resource_id,
            "metric": a.metric_name,
            "kind": a.kind,
            "severity": a.severity,
            "last_hour_average": a.recent_value,
            "seven_day_average": a.baseline_mean,
            "standard_deviations_from_normal": a.z_score,
        }
        for a in batch
    ]
    response = client.messages.create(
        model=EXPLAIN_MODEL,
        max_tokens=1500,
        system=EXPLAIN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    parsed = json.loads(response.content[0].text)
    if not isinstance(parsed, list) or len(parsed) != len(batch):
        return None
    out = []
    for item in parsed:
        if not isinstance(item, dict):
            return None
        description = str(item.get("description") or "").strip()
        recommendation = str(item.get("recommendation") or "").strip()
        if not description or not recommendation:
            return None
        out.append((description[:600], recommendation[:400]))
    return out


async def explain(anomalies: List[Anomaly], client: Any = None) -> List[Tuple[str, str]]:
    """(description, recommendation) for each anomaly, in order.

    Built-in wording is the default and the fallback. Claude's version is used
    only if it comes back well-formed and one-for-one; any failure at all
    leaves the built-in text in place, so an outage there never costs an alert.
    """
    texts = [describe(a) for a in anomalies]
    if client is None or not anomalies:
        return texts
    batch = anomalies[:EXPLAIN_LIMIT]
    try:
        worded = await asyncio.to_thread(_explain_with_claude, client, batch)
    except Exception as exc:  # noqa: BLE001 — any failure falls back to built-in text
        logger.warning("Anomaly explanation unavailable, using built-in wording: %s", exc)
        return texts
    if worded:
        texts[: len(worded)] = worded
    return texts


def _is_fresh(computed_at: Any, now: datetime) -> bool:
    if not computed_at:
        return False
    try:
        when = datetime.fromisoformat(str(computed_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if not when.tzinfo:
        when = when.replace(tzinfo=timezone.utc)
    return now - when < BASELINE_MAX_AGE


async def _baseline(
    customer_id: str,
    ts_service: TimestreamQueryService,
    db_service: DynamoDBService,
) -> List[Dict[str, Any]]:
    """The 7-day baseline, computed at most every few hours.

    Blocking DynamoDB work, so it runs on a worker thread: on the event loop it
    froze every request this worker was serving, health checks included.
    """
    now = datetime.now(timezone.utc)
    stored = await asyncio.to_thread(db_service.get_baseline, customer_id)
    if stored and _is_fresh(stored.get("computed_at"), now) and stored.get("series"):
        return stored["series"]

    series = await asyncio.to_thread(ts_service.get_7day_summary, customer_id)
    if series:
        await asyncio.to_thread(db_service.put_baseline, customer_id, series)
    return series


async def detect_anomalies_for_customer(
    customer_id: str,
    ts_service: TimestreamQueryService,
    db_service: DynamoDBService,
    notif_service: NotificationService,
    claude_client: Any = None,
    customer: Optional[Dict[str, Any]] = None,
) -> int:
    """Detect, explain, record and deliver anomalies for one customer.

    Returns the number of new alerts created.
    """
    baseline = await _baseline(customer_id, ts_service, db_service)
    recent = await asyncio.to_thread(ts_service.get_last_hour, customer_id)
    if not baseline or not recent:
        return 0

    anomalies = detect(baseline, recent)
    if not anomalies:
        return 0

    active = db_service.get_alerts(customer_id, status_filter="active")
    active_keys = {
        f"{a.get('service')}#{a.get('resource_id')}#{a.get('metric_name')}"
        for a in active
        if a.get("type") == "ai_anomaly"
    }
    fresh = [a for a in anomalies if f"{a.service}#{a.resource_id}#{a.metric_name}" not in active_keys]
    if not fresh:
        return 0

    texts = await explain(fresh, claude_client)
    if customer is None:
        customer = db_service.get_customer(customer_id) or {"customer_id": customer_id}

    new_alerts = 0
    for anomaly, (description, recommendation) in zip(fresh, texts):
        key = f"{anomaly.service}#{anomaly.resource_id}#{anomaly.metric_name}"
        alert_id = db_service.create_alert(customer_id, {
            # The type string is kept for compatibility with stored alerts;
            # detection itself is statistical, see the module docstring.
            "type": "ai_anomaly",
            "severity": anomaly.severity,
            "service": anomaly.service,
            "resource_id": anomaly.resource_id,
            "metric_name": anomaly.metric_name,
            "current_value": _dec(anomaly.recent_value),
            "description": description,
            "recommendation": recommendation,
            "detection": {
                "method": anomaly.kind,
                "z_score": _dec(anomaly.z_score),
                "baseline_mean": _dec(anomaly.baseline_mean),
                "baseline_stddev": _dec(anomaly.baseline_stddev),
                "samples": anomaly.samples,
            },
        }, dedupe_key=f"anomaly:{key}")

        if not alert_id:
            continue
        new_alerts += 1
        active_keys.add(key)
        await notif_service.send_ops_alert(
            customer_id=customer_id,
            service=anomaly.service,
            resource_id=anomaly.resource_id,
            metric_name="Anomaly",
            severity=anomaly.severity,
            description=description,
        )
        try:
            await notif_service.deliver_to_customer(
                customer,
                service=anomaly.service,
                resource_id=anomaly.resource_id,
                metric_name=anomaly.metric_name,
                severity=anomaly.severity,
                current_value=anomaly.recent_value,
                description=f"{description}\n\n{recommendation}",
            )
        except Exception as exc:  # noqa: BLE001 — delivery must not stop detection
            logger.warning("Customer delivery failed for %s: %s", customer_id, exc)

    return new_alerts


def _claude_client() -> Any:
    config = load_config()
    if not config.anthropic_api_key:
        logger.info("No Anthropic key configured: anomalies will use built-in wording")
        return None
    from anthropic import Anthropic
    return Anthropic(api_key=config.anthropic_api_key)


async def run_anomaly_detection_for_customer(customer_id: str) -> int:
    """One detection pass for one customer, with fresh services."""
    db = DynamoDBService()
    return await detect_anomalies_for_customer(
        customer_id, TimestreamQueryService(), db, NotificationService(),
        _claude_client(), db.get_customer(customer_id),
    )


async def anomaly_detection_loop() -> None:
    """Background task: detection every 30 minutes for every active customer."""
    client = _claude_client()
    ts_service = TimestreamQueryService()
    db_service = DynamoDBService()
    notif_service = NotificationService()
    logger.info("Anomaly detection loop started (interval: %d min)", INTERVAL_SECONDS // 60)
    await asyncio.sleep(STARTUP_DELAY_SECONDS)

    while True:
        try:
            for customer in await asyncio.to_thread(db_service.list_customers):
                if customer.get("status") != "active":
                    continue
                await detect_anomalies_for_customer(
                    customer["customer_id"], ts_service, db_service,
                    notif_service, client, customer,
                )
        except Exception as exc:  # noqa: BLE001
            logger.error("Anomaly detection loop error: %s", exc)

        await asyncio.sleep(INTERVAL_SECONDS)
