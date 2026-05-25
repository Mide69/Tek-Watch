"""Alerts router — threshold and AI anomaly alerts."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from auth.dependencies import CustomerContext, get_current_customer
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
async def get_alerts(
    customer: CustomerContext = Depends(get_current_customer),
    status_filter: Optional[str] = Query(None, description="Filter by status: active, acknowledged, resolved"),
):
    """Get all alerts for the authenticated customer."""
    db = DynamoDBService()
    alerts = db.get_alerts(customer.customer_id, status_filter)
    return {"alerts": alerts}


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str = Path(...),
    customer: CustomerContext = Depends(get_current_customer),
):
    """Acknowledge an alert."""
    db = DynamoDBService()
    success = db.acknowledge_alert(customer.customer_id, alert_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found or already acknowledged",
        )
    return {"status": "acknowledged", "alert_id": alert_id}
