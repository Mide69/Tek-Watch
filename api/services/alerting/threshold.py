"""Threshold alert evaluation engine — runs every 5 minutes."""
import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import load_config
from services.dynamodb import DynamoDBService
from services.notifications import NotificationService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

# Wait before the first pass so a starting task can answer health checks
# first. The anomaly loop waits 120s; staggering them keeps the two from
# hitting DynamoDB at the same moment.
STARTUP_DELAY_SECONDS = 90

_OPERATOR_MAP = {
    "gt":  lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt":  lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
}


def _dec(value: Optional[float]) -> Optional[Decimal]:
    """DynamoDB rejects Python floats, so every number stored is a Decimal.

    The comparison needs a float and the stored item needs a Decimal. This was
    never hit before because the evaluator read the events table and no row's
    value ever parsed as a number, so it never reached the write.
    """
    if value is None:
        return None
    return Decimal(str(round(float(value), 6)))


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
    # Every DynamoDB call here is blocking boto3. Run on the event loop they
    # freeze this worker's requests, health checks included.
    customer_thresholds = await asyncio.to_thread(db_service.get_thresholds, customer_id)
    default_thresholds = await asyncio.to_thread(db_service.get_thresholds, "DEFAULT")

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
    active_alerts = await asyncio.to_thread(db_service.get_alerts, customer_id, "active")
    active_keys = {
        f"{a.get('service')}#{a.get('resource_id')}#{a.get('metric_name')}"
        for a in active_alerts
    }

    # One query for the whole window, indexed by service and metric. This was
    # a query per threshold, which multiplied the reads by the number of
    # thresholds on every pass.
    readings = await asyncio.to_thread(
        ts_service.get_latest_numeric_metrics, customer_id, None, "5m"
    )
    by_service_metric: Dict[tuple, List[Dict[str, Any]]] = {}
    for row in readings:
        by_service_metric.setdefault(
            (row.get("service"), row.get("metric_name")), []
        ).append(row)

    new_alerts = 0
    customer_record = None   # fetched once, only if an alert actually fires

    for threshold_key, threshold in threshold_map.items():
        if not threshold.get("enabled", True):
            continue

        service = threshold.get("service", "")
        metric_name = threshold.get("metric_name", "")
        operator = threshold.get("operator", "gt")
        threshold_value = float(threshold.get("threshold_value", 0))
        severity = threshold.get("severity", "medium")

        # Readings for this service and metric, from the single query above.
        # This used to call get_resources_by_service, which reads the events
        # table — string states only — so float() failed on every row and no
        # threshold could fire.
        for resource in by_service_metric.get((service, metric_name), []):
            resource_id = resource.get("resource_id", "")

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

            # Create new alert. The active_keys check above is a cheap local
            # filter; dedupe_key is what actually prevents two API replicas from
            # both raising this alert, since each holds its own active_keys.
            alert = {
                "type": "threshold",
                "severity": severity,
                "service": service,
                "resource_id": resource_id,
                "resource_name": resource.get("resource_name", resource_id),
                "metric_name": metric_name,
                "current_value": _dec(current_value),
                "threshold_value": _dec(threshold_value),
                "description": (
                    f"{metric_name} is {current_value:.2f} "
                    f"({operator} {threshold_value})"
                ),
            }
            alert_id = await asyncio.to_thread(
                db_service.create_alert, customer_id, alert, dedupe_key=alert_key
            )

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
                # Tell the customer too. Alerts used to reach only our own ops
                # topic; the settings customers saved were never read.
                try:
                    if customer_record is None:
                        customer_record = await asyncio.to_thread(
                            db_service.get_customer, customer_id
                        ) or {"customer_id": customer_id}
                    await notif_service.deliver_to_customer(
                        customer_record,
                        service=service,
                        resource_id=resource_id,
                        metric_name=metric_name,
                        severity=severity,
                        current_value=float(current_value) if current_value is not None else None,
                        threshold_value=float(threshold_value) if threshold_value is not None else None,
                    )
                except Exception as exc:  # noqa: BLE001 — delivery must not stop evaluation
                    logger.warning("Customer delivery failed for %s: %s", customer_id, exc)

    return new_alerts


async def threshold_evaluation_loop() -> None:
    """Background task — evaluates thresholds every 5 minutes."""
    ts_service = TimestreamQueryService()
    db_service = DynamoDBService()
    notif_service = NotificationService()

    logger.info("Threshold evaluation loop started (interval: 5 min)")
    # The first pass used to start the moment the process booted, inside the
    # load balancer's 60-second grace period, with every read on the event
    # loop. A task that cannot answer health checks in time is replaced, and
    # the deployment is rolled back.
    await asyncio.sleep(STARTUP_DELAY_SECONDS)

    while True:
        try:
            customers = await asyncio.to_thread(db_service.list_customers)
            active = [c for c in customers if c.get("status") == "active"]

            for customer in active:
                await evaluate_thresholds_for_customer(
                    customer["customer_id"], ts_service, db_service, notif_service
                )

        except Exception as exc:  # noqa: BLE001
            logger.error("Threshold evaluation loop error: %s", exc)

        await asyncio.sleep(5 * 60)  # 5 minutes
