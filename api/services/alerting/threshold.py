"""Threshold alert evaluation engine — runs every 5 minutes."""
import asyncio
import logging
from typing import Any, Dict, List

from config import load_config
from services.dynamodb import DynamoDBService
from services.notifications import NotificationService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

_OPERATOR_MAP = {
    "gt":  lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt":  lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
}


def _evaluate(value: float, operator: str, threshold: float) -> bool:
    """Evaluate a threshold condition."""
    fn = _OPERATOR_MAP.get(operator)
    return fn(value, threshold) if fn else False


async def evaluate_thresholds_for_customer(
    customer_id: str,
    ts_service: TimestreamQueryService,
    db_service: DynamoDBService,
    notif_service: NotificationService,
) -> int:
    """Evaluate all thresholds for a single customer.

    Returns:
        Number of new alerts created.
    """
    # Get effective thresholds (customer overrides + defaults)
    customer_thresholds = db_service.get_thresholds(customer_id)
    default_thresholds = db_service.get_thresholds("DEFAULT")

    # Customer overrides take precedence
    threshold_map: Dict[str, Dict[str, Any]] = {}
    for t in default_thresholds:
        key = f"{t.get('service')}#{t.get('metric_name')}"
        threshold_map[key] = t
    for t in customer_thresholds:
        key = f"{t.get('service')}#{t.get('metric_name')}"
        threshold_map[key] = t

    if not threshold_map:
        return 0

    # Get existing active alerts to avoid duplicates
    active_alerts = db_service.get_alerts(customer_id, status_filter="active")
    active_keys = {
        f"{a.get('service')}#{a.get('resource_id')}#{a.get('metric_name')}"
        for a in active_alerts
    }

    new_alerts = 0

    for threshold_key, threshold in threshold_map.items():
        if not threshold.get("enabled", True):
            continue

        service = threshold.get("service", "")
        metric_name = threshold.get("metric_name", "")
        operator = threshold.get("operator", "gt")
        threshold_value = float(threshold.get("threshold_value", 0))
        severity = threshold.get("severity", "medium")

        # Query latest values for this service/metric
        resources = ts_service.get_resources_by_service(customer_id, service, "5m")

        for resource in resources:
            resource_id = resource.get("resource_id", "")
            if resource.get("metric_name") != metric_name:
                continue

            try:
                current_value = float(resource.get("value", 0))
            except (TypeError, ValueError):
                continue

            if not _evaluate(current_value, operator, threshold_value):
                continue

            # Check for existing active alert
            alert_key = f"{service}#{resource_id}#{metric_name}"
            if alert_key in active_keys:
                continue

            # Create new alert
            alert_id = db_service.create_alert(customer_id, {
                "type": "threshold",
                "severity": severity,
                "service": service,
                "resource_id": resource_id,
                "resource_name": resource.get("resource_name", resource_id),
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold_value": threshold_value,
                "description": (
                    f"{metric_name} is {current_value:.2f} "
                    f"({operator} {threshold_value})"
                ),
            })

            if alert_id:
                new_alerts += 1
                active_keys.add(alert_key)
                await notif_service.send_ops_alert(
                    customer_id=customer_id,
                    service=service,
                    resource_id=resource_id,
                    metric_name=metric_name,
                    severity=severity,
                    current_value=current_value,
                    threshold_value=threshold_value,
                )

    return new_alerts


async def threshold_evaluation_loop() -> None:
    """Background task — evaluates thresholds every 5 minutes."""
    ts_service = TimestreamQueryService()
    db_service = DynamoDBService()
    notif_service = NotificationService()

    logger.info("Threshold evaluation loop started (interval: 5 min)")

    while True:
        try:
            customers = db_service.list_customers()
            active = [c for c in customers if c.get("status") == "active"]

            for customer in active:
                await evaluate_thresholds_for_customer(
                    customer["customer_id"], ts_service, db_service, notif_service
                )

        except Exception as exc:  # noqa: BLE001
            logger.error("Threshold evaluation loop error: %s", exc)

        await asyncio.sleep(5 * 60)  # 5 minutes
