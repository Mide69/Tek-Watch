"""
Overview router — dashboard home page summary data.

GET /api/v1/overview
  - Total resources count
  - Active alarms count
  - Open security findings count
  - Estimated monthly cost
  - Top 5 active CloudWatch alarms
  - Top 3 GuardDuty findings
  - Cost trend (this month vs last month)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.dynamodb import DynamoDBService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/overview")
async def get_overview(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None, description="Filter by AWS region"),
):
    """Get dashboard overview summary."""
    ts_service = TimestreamQueryService()
    db_service = DynamoDBService()
    
    # Get customer profile for agent status
    customer_profile = db_service.get_customer(customer.customer_id)
    agent_status = {
        "status": customer_profile.get("agent_status", "unknown") if customer_profile else "unknown",
        "last_seen": customer_profile.get("last_agent_seen") if customer_profile else None,
    }
    
    # Active alerts count
    active_alerts = db_service.get_alerts(customer.customer_id, status_filter="active")
    active_alarms_count = len([a for a in active_alerts if a.get("type") == "threshold"])
    security_findings_count = len([a for a in active_alerts if a.get("severity") in ["high", "critical"]])
    
    # Get top 5 alarms
    top_alarms = active_alerts[:5]
    
    # Estimated monthly cost
    monthly_cost = ts_service.get_latest_metric(
        customer.customer_id, "cost_explorer", "forecast", "forecasted_monthly_spend"
    )
    
    # Total resources (approximate from recent metrics)
    resources = ts_service.get_resources_by_service(customer.customer_id, "ec2", "5m")
    total_resources = len(set(r.get("resource_id") for r in resources))
    
    return {
        "total_resources": total_resources,
        "active_alarms": active_alarms_count,
        "security_findings": security_findings_count,
        "estimated_monthly_cost": monthly_cost or 0,
        "top_alarms": top_alarms,
        "agent_status": agent_status,
    }
