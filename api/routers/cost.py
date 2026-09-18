"""Cost router — Cost Explorer data and forecasts."""
import logging
from datetime import datetime, timezone

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
    
    # Month-to-date total.
    #
    # daily_costs covers 30 days, which spans the previous month, so summing
    # all of it was never month-to-date — it was a rolling 30-day total
    # labelled MTD. (It was also counting each day once per collection until
    # get_daily_costs started folding by calendar day.)
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    mtd_total = sum(
        float(row.get("cost", 0))
        for row in daily_costs
        if str(row.get("time", "")).startswith(this_month)
    )

    # The agent publishes the forecast against the customer id, as
    # "forecasted_monthly_cost". Asking for resource "forecast" and metric
    # "forecasted_monthly_spend" matched nothing, so this was always None and
    # the page showed a forecast of zero next to real daily costs.
    forecast = ts.get_latest_metric(
        customer.customer_id,
        "cost_explorer",
        customer.customer_id,
        "forecasted_monthly_cost",
    )
    
    return {
        "mtd_total": round(mtd_total, 2),
        "forecasted_monthly": round(forecast or 0, 2),
        # The currency AWS bills this account in, so the page stops assuming
        # dollars. Taken from the most recent day that reported one.
        "currency": daily_costs[-1]["currency"] if daily_costs else "USD",
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
