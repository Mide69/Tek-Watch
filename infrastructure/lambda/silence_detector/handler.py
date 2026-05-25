"""
Silence Detector Lambda
=======================
Runs on a schedule (every 15 minutes via EventBridge).

For each active customer it checks when the last heartbeat was received
from the monitoring agent. If the gap exceeds the silence threshold
(default: 20 minutes), it creates or updates a CRITICAL alert and
optionally sends a notification.

Environment variables:
    ALERTS_TABLE        DynamoDB table name for alerts
    HEARTBEATS_TABLE    DynamoDB table name for agent heartbeats
    SILENCE_THRESHOLD   Minutes before a customer is considered silent (default: 20)
    NOTIFICATION_TOPIC  Optional SNS topic ARN for operator notifications
    LOG_LEVEL           Logging level (default: INFO)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# ─── Config ──────────────────────────────────────────────────────────────────

ALERTS_TABLE     = os.environ.get("ALERTS_TABLE",     "tek-watch-alerts")
HEARTBEATS_TABLE = os.environ.get("HEARTBEATS_TABLE", "tek-watch-heartbeats")
SILENCE_MIN      = int(os.environ.get("SILENCE_THRESHOLD", "20"))
NOTIFY_TOPIC     = os.environ.get("NOTIFICATION_TOPIC", "")

# ─── AWS clients (lazy, module-level for Lambda container reuse) ──────────────

_dynamodb = None
_sns      = None


def _get_dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


def _get_sns():
    global _sns
    if _sns is None and NOTIFY_TOPIC:
        _sns = boto3.client("sns")
    return _sns


# ─── Core logic ──────────────────────────────────────────────────────────────

def get_all_customers(ddb) -> list[dict]:
    """Return all active customers from the heartbeats table."""
    try:
        table = ddb.Table(HEARTBEATS_TABLE)
        result = table.scan(
            ProjectionExpression="customer_id, last_heartbeat, #st",
            ExpressionAttributeNames={"#st": "status"},
        )
        return result.get("Items", [])
    except ClientError as exc:
        logger.error("Failed to scan heartbeats table: %s", exc)
        return []


def is_silent(last_heartbeat_iso: str, threshold_minutes: int) -> bool:
    """Return True if the agent has been silent longer than threshold_minutes."""
    try:
        ts   = (last_heartbeat_iso or "").replace("Z", "+00:00")
        last = datetime.fromisoformat(ts)
        gap  = datetime.now(timezone.utc) - last
        return gap > timedelta(minutes=threshold_minutes)
    except (ValueError, TypeError, AttributeError):
        return True   # treat unparseable or missing timestamp as silent


def build_alert(customer_id: str, last_heartbeat: str, gap_minutes: float) -> dict:
    """Build the alert record for a silenced agent."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "alert_id":       f"SILENCE-{customer_id}",
        "customer_id":    customer_id,
        "severity":       "critical",
        "status":         "active",
        "type":           "agent_silence",
        "service":        "agent",
        "resource":       f"monitoring-agent-{customer_id}",
        "description":    (
            f"No heartbeat received from monitoring agent for customer {customer_id} "
            f"in the last {gap_minutes:.0f} minutes. "
            f"Last seen: {last_heartbeat}. "
            f"Infrastructure data may be stale."
        ),
        "triggered_at":   now,
        "current_value":  round(gap_minutes, 1),
        "threshold_value": float(SILENCE_MIN),
        "recommendation": (
            "1. Check ECS task status for the monitoring agent. "
            "2. Review CloudWatch logs for the agent task. "
            "3. Verify IAM permissions have not changed. "
            "4. Confirm SQS queue is reachable from the agent VPC."
        ),
        "last_heartbeat": last_heartbeat,
        "updated_at":     now,
    }


def upsert_alert(ddb, alert: dict) -> None:
    """Write (or overwrite) the silence alert to DynamoDB."""
    try:
        table = ddb.Table(ALERTS_TABLE)
        table.put_item(Item=alert)
        logger.info("Upserted silence alert for customer %s", alert["customer_id"])
    except ClientError as exc:
        logger.error("Failed to write alert for %s: %s", alert["customer_id"], exc)


def resolve_alert(ddb, customer_id: str) -> None:
    """Remove or resolve a previously raised silence alert."""
    try:
        table = ddb.Table(ALERTS_TABLE)
        table.update_item(
            Key={"alert_id": f"SILENCE-{customer_id}"},
            UpdateExpression="SET #st = :resolved, resolved_at = :now",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":resolved": "resolved",
                ":now": datetime.now(timezone.utc).isoformat(),
            },
            ConditionExpression="attribute_exists(alert_id)",
        )
        logger.info("Resolved silence alert for customer %s", customer_id)
    except ddb.meta.client.exceptions.ConditionalCheckFailedException:
        pass   # alert didn't exist — nothing to resolve
    except ClientError as exc:
        logger.error("Failed to resolve alert for %s: %s", customer_id, exc)


def notify_operator(customer_id: str, gap_minutes: float) -> None:
    """Send an SNS notification if a topic is configured."""
    sns = _get_sns()
    if sns is None:
        return
    try:
        sns.publish(
            TopicArn=NOTIFY_TOPIC,
            Subject=f"[TekWatch] Agent SILENT — {customer_id}",
            Message=json.dumps({
                "customer_id": customer_id,
                "gap_minutes": round(gap_minutes, 1),
                "threshold_minutes": SILENCE_MIN,
                "message": (
                    f"The monitoring agent for customer {customer_id} has not sent a heartbeat "
                    f"for {gap_minutes:.0f} minutes (threshold: {SILENCE_MIN} minutes)."
                ),
            }, indent=2),
        )
        logger.info("Sent silence notification for customer %s", customer_id)
    except ClientError as exc:
        logger.error("Failed to send SNS notification: %s", exc)


# ─── Lambda entry point ───────────────────────────────────────────────────────

def handler(event: dict, context) -> dict:
    """
    Lambda handler — invoked by EventBridge scheduler every 15 minutes.

    Returns:
        dict with keys:
            checked    — number of customers evaluated
            silenced   — number of customers currently silent
            resolved   — number of previously-silent customers now recovered
    """
    logger.info("Silence detector starting. Threshold=%d minutes", SILENCE_MIN)
    ddb = _get_dynamodb()

    customers   = get_all_customers(ddb)
    silenced    = 0
    resolved    = 0
    now         = datetime.now(timezone.utc)

    for customer in customers:
        customer_id    = customer.get("customer_id", "unknown")
        last_heartbeat = customer.get("last_heartbeat", "")

        if not last_heartbeat:
            logger.warning("Customer %s has no heartbeat record", customer_id)
            continue

        try:
            last_dt    = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
            gap_minutes = (now - last_dt).total_seconds() / 60
        except (ValueError, TypeError):
            logger.warning("Unparseable heartbeat for %s: %r", customer_id, last_heartbeat)
            gap_minutes = float("inf")

        if gap_minutes > SILENCE_MIN:
            logger.warning(
                "Customer %s SILENT: last heartbeat %.1f minutes ago",
                customer_id, gap_minutes,
            )
            alert = build_alert(customer_id, last_heartbeat, gap_minutes)
            upsert_alert(ddb, alert)
            notify_operator(customer_id, gap_minutes)
            silenced += 1
        else:
            resolve_alert(ddb, customer_id)
            resolved += 1

    result = {
        "checked":  len(customers),
        "silenced": silenced,
        "resolved": resolved,
    }
    logger.info("Silence detector complete: %s", result)
    return result
