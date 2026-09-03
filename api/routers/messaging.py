"""Messaging router — SQS queues and SNS topics."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.inventory_view import dim, flag, num
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sqs")
async def get_sqs_queues(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get SQS queue inventory and depth metrics."""
    ts = TimestreamQueryService()
    queues = [
        {
            "queue_name": q["resource_name"],
            "region": q.get("region") or "",
            "type": "FIFO" if q["resource_name"].endswith(".fifo") else "Standard",
            "messages_visible": num(q, "approximate_number_of_messages_visible"),
            "messages_inflight": num(q, "messages_in_flight"),
            "oldest_message_age": num(q, "approximate_age_of_oldest_message_seconds"),
            "is_dlq": flag(q, "is_dlq"),
            # The collector does not link a queue to its redrive target, so
            # there is no honest way to name a queue's DLQ or count its depth.
            "dlq": None,
            "dlq_count": None,
            "throughput": None,
            "last_seen": q.get("last_seen"),
        }
        for q in ts.get_service_inventory(customer.customer_id, "sqs")
    ]
    if region:
        queues = [q for q in queues if q["region"] == region]
    return {"queues": queues}


@router.get("/sns")
async def get_sns_topics(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get SNS topic inventory and delivery metrics."""
    ts = TimestreamQueryService()
    topics = []
    for t in ts.get_service_inventory(customer.customer_id, "sns"):
        delivered = num(t, "messages_delivered_24h")
        failed = num(t, "notifications_failed_24h")
        attempted = None
        if delivered is not None and failed is not None:
            attempted = delivered + failed

        topics.append({
            "topic_name": t["resource_name"],
            "region": t.get("region") or "",
            "subscriptions": num(t, "subscriptions_count")
            or (float(dim(t, "subscriptions_count")) if dim(t, "subscriptions_count").isdigit() else None),
            "messages_day": num(t, "messages_published_24h"),
            "delivery_success": (
                round(delivered / attempted * 100, 1)
                if attempted else (100.0 if delivered is not None else None)
            ),
            "is_fifo": flag(t, "is_fifo"),
            "last_seen": t.get("last_seen"),
        })

    if region:
        topics = [t for t in topics if t["region"] == region]
    return {"topics": topics}
