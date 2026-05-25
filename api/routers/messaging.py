"""Messaging router — SQS and SNS metrics."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/sqs")
async def get_sqs_queues(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get SQS queue metrics."""
    ts = TimestreamQueryService()
    queues = ts.get_resources_by_service(customer.customer_id, "sqs")
    return {"queues": queues}


@router.get("/sns")
async def get_sns_topics(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get SNS topic metrics."""
    ts = TimestreamQueryService()
    topics = ts.get_resources_by_service(customer.customer_id, "sns")
    return {"topics": topics}
