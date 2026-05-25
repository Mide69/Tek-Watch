"""Cost router — Cost Explorer data and forecasts."""
import logging

from fastapi import APIRouter, Depends

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/summary")
async def get_cost_summary(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get cost overview with MTD, forecast, and trend."""
    ts = TimestreamQueryService()
    
    # Get daily costs for chart
    daily_costs = ts.get_daily_costs(customer.customer_id)
    
    # Calculate MTD total
    mtd_total = sum(float(row.get("cost", 0)) for row in daily_costs)
    
    # Get forecast (latest forecast metric)
    forecast = ts.get_latest_metric(
        customer.customer_id, "cost_explorer", "forecast", "forecasted_monthly_spend"
    )
    
    return {
        "mtd_total": round(mtd_total, 2),
        "forecasted_monthly": round(forecast or 0, 2),
        "daily_costs": daily_costs,
    }


@router.get("/breakdown")
async def get_cost_breakdown(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get per-service cost breakdown."""
    ts = TimestreamQueryService()
    breakdown = ts.get_service_costs(customer.customer_id)
    return {"breakdown": breakdown}
