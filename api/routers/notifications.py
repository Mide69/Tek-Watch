"""Notifications router — customer notification preferences."""
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.dependencies import CustomerContext, get_current_customer
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_SEVERITIES = {"low", "warning", "high", "critical"}


class NotificationPreferences(BaseModel):
    email_enabled: bool = True
    email_address: str | None = None
    slack_webhook_url: str | None = None
    min_severity: str = "warning"
    pagerduty_integration_key: str | None = None


def _defaults() -> dict:
    return NotificationPreferences().model_dump()


@router.get("/preferences")
async def get_preferences(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Return the authenticated customer's notification preferences."""
    db = DynamoDBService()
    customer_record = db.get_customer(customer.customer_id)
    prefs = (customer_record or {}).get("notification_preferences") or _defaults()
    return {"preferences": prefs}


@router.put("/preferences")
async def update_preferences(
    prefs: NotificationPreferences,
    customer: CustomerContext = Depends(get_current_customer),
):
    """Update notification preferences for the authenticated customer."""
    if prefs.min_severity not in VALID_SEVERITIES:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"min_severity must be one of: {', '.join(sorted(VALID_SEVERITIES))}",
        )

    db = DynamoDBService()
    db.update_customer(
        customer.customer_id,
        {"notification_preferences": prefs.model_dump()},
    )
    logger.info("Notification preferences updated: customer=%s", customer.customer_id)
    return {"status": "updated", "preferences": prefs.model_dump()}
