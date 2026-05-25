"""Agent router — agent health status and heartbeat history."""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.dynamodb import DynamoDBService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()

# Collectors that are always enabled
ALL_COLLECTORS = [
    "ec2", "lambda", "rds", "sqs", "sns", "dynamodb", "ecs", "eks",
    "elasticache", "elb", "vpc", "cloudwatch_alarms", "guardduty",
    "acm", "cloudtrail", "security_hub", "config",
    "iam", "cost_explorer", "s3", "cloudfront", "route53", "trusted_advisor",
]


def _agent_status_from_last_seen(last_seen: Optional[str]) -> str:
    """Derive agent status from last heartbeat timestamp."""
    if not last_seen:
        return "silent"
    try:
        ts = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        age_minutes = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        if age_minutes <= 10:
            return "healthy"
        if age_minutes <= 20:
            return "degraded"
        return "unhealthy"
    except (ValueError, TypeError):
        return "unknown"


@router.get("/health")
async def get_agent_health(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get agent health status, heartbeat history, and collection metrics."""
    db = DynamoDBService()
    ts = TimestreamQueryService()

    customer_profile = db.get_customer(customer.customer_id)
    if not customer_profile:
        return {
            "customer_id":           customer.customer_id,
            "status":                "unknown",
            "last_heartbeat":        None,
            "last_collection_time":  None,
            "collections_24h":       0,
            "failed_collections_24h": 0,
            "regions_monitored":     [],
            "collectors_enabled":    ALL_COLLECTORS,
        }

    last_seen = customer_profile.get("last_agent_seen")
    stored_status = customer_profile.get("agent_status", "unknown")

    # Derive a more precise status from the timestamp
    derived_status = _agent_status_from_last_seen(last_seen)
    # Use stored status if it's "offline" (set by silence detector), otherwise derive
    status = stored_status if stored_status == "offline" else derived_status

    # Query heartbeat records from Timestream for the last 24h
    heartbeats = ts.get_time_series(
        customer_id=customer.customer_id,
        resource_id=customer.customer_id,
        metric_name="heartbeat",
        time_range="24h",
    )

    collections_24h = len(heartbeats)
    failed_24h = 0
    regions_monitored: list[str] = []

    # Parse the most recent heartbeat dimensions for region list
    recent_events = ts.get_resources_by_service(
        customer.customer_id, "agent", "24h"
    )
    for event in recent_events:
        if event.get("metric_name") == "heartbeat":
            regions_str = event.get("regions_collected", "")
            if regions_str:
                regions_monitored = [r.strip() for r in regions_str.split(",") if r.strip()]
            errors = event.get("total_errors", "0")
            try:
                if int(errors) > 0:
                    failed_24h += 1
            except (ValueError, TypeError):
                pass
            break

    return {
        "customer_id":            customer.customer_id,
        "status":                 status,
        "last_heartbeat":         last_seen,
        "last_collection_time":   last_seen,
        "collections_24h":        collections_24h,
        "failed_collections_24h": failed_24h,
        "regions_monitored":      regions_monitored or ["eu-west-2"],
        "collectors_enabled":     ALL_COLLECTORS,
        "version":                "1.0.0",
    }
