"""Metrics router — time-series data for resource drilldown."""
import logging

from fastapi import APIRouter, Depends, Path, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{resource_id}")
async def get_resource_metrics(
    resource_id: str = Path(...),
    metric_name: str = Query(..., description="Metric name to query"),
    time_range: str = Query("24h", description="Time range: 24h, 7d, 30d, 90d"),
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get time-series data for a specific resource metric."""
    ts = TimestreamQueryService()
    
    time_series = ts.get_time_series(
        customer_id=customer.customer_id,
        resource_id=resource_id,
        metric_name=metric_name,
        time_range=time_range,
    )
    
    return {
        "resource_id": resource_id,
        "metric_name": metric_name,
        "time_range": time_range,
        "data": time_series,
    }
