"""Storage router — S3 bucket inventory and metrics."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.inventory_view import dim, flag, num
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/s3")
async def get_s3_buckets(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get S3 bucket inventory and metrics.

    This returned the raw metric rows — one per bucket per metric, carrying
    only metric_name and value. The page expects a bucket, and read
    `b.object_count.toLocaleString()` on the first of them, so the whole
    Storage page died on "Cannot read properties of undefined". The rows also
    came from the events table alone, where a bucket's size and object count
    do not live, so even a page that survived had no numbers to show.
    """
    ts = TimestreamQueryService()
    buckets = [
        {
            "bucket_name": b["resource_name"],
            "region": dim(b, "bucket_region") or b.get("region") or "",
            "size_bytes": num(b, "bucket_size_bytes"),
            "object_count": num(b, "number_of_objects"),
            # Cost Explorer reports per service, not per bucket, so there is no
            # honest per-bucket figure to give. None, and the page shows a dash.
            "cost_mtd": None,
            "versioning": flag(b, "versioning_enabled"),
            "encryption": dim(b, "encryption_algorithm")
            or ("enabled" if flag(b, "encryption_enabled") else None),
            "public_access_blocked": flag(b, "public_access_blocked"),
            "last_seen": b.get("last_seen"),
        }
        for b in ts.get_service_inventory(customer.customer_id, "s3")
    ]

    if region:
        buckets = [b for b in buckets if b["region"] == region]

    return {"buckets": buckets}
