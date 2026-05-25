"""Admin thresholds router — threshold configuration management."""
import logging

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from auth.dependencies import AdminContext, get_current_admin
from services.dynamodb import DynamoDBService

logger = logging.getLogger(__name__)
router = APIRouter()


class ThresholdConfig(BaseModel):
    """Threshold configuration model."""
    operator: str  # "gt", "lt", "gte", "lte"
    threshold_value: float
    severity: str  # "low", "medium", "high", "critical"
    enabled: bool = True


@router.get("")
async def get_default_thresholds(
    admin: AdminContext = Depends(get_current_admin),
):
    """Get default thresholds that apply to all customers."""
    db = DynamoDBService()
    thresholds = db.get_thresholds("DEFAULT")
    return {"thresholds": thresholds}


@router.put("")
async def update_default_threshold(
    service: str,
    metric_name: str,
    config: ThresholdConfig,
    admin: AdminContext = Depends(get_current_admin),
):
    """Update a default threshold."""
    db = DynamoDBService()
    success = db.upsert_threshold(
        "DEFAULT",
        service,
        metric_name,
        config.model_dump(),
    )
    return {"status": "updated" if success else "failed"}


@router.get("/{customer_id}")
async def get_customer_thresholds(
    customer_id: str = Path(...),
    admin: AdminContext = Depends(get_current_admin),
):
    """Get customer-specific threshold overrides."""
    db = DynamoDBService()
    thresholds = db.get_thresholds(customer_id)
    return {"customer_id": customer_id, "thresholds": thresholds}


@router.put("/{customer_id}")
async def update_customer_threshold(
    customer_id: str,
    service: str,
    metric_name: str,
    config: ThresholdConfig,
    admin: AdminContext = Depends(get_current_admin),
):
    """Set a customer-specific threshold override."""
    db = DynamoDBService()
    success = db.upsert_threshold(
        customer_id,
        service,
        metric_name,
        config.model_dump(),
    )
    return {"status": "updated" if success else "failed", "customer_id": customer_id}
