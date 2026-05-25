"""Storage router — S3 bucket metrics."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/s3")
async def get_s3_buckets(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get S3 bucket inventory and metrics."""
    ts = TimestreamQueryService()
    buckets = ts.get_resources_by_service(customer.customer_id, "s3")
    return {"buckets": buckets}
