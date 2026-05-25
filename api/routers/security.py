"""Security router — GuardDuty, IAM, ACM, CloudWatch Alarms."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/guardduty")
async def get_guardduty_findings(
    customer: CustomerContext = Depends(get_current_customer),
    severity: Optional[str] = Query(None),
):
    """Get GuardDuty findings."""
    ts = TimestreamQueryService()
    findings = ts.get_resources_by_service(customer.customer_id, "guardduty")
    return {"findings": findings}


@router.get("/cloudtrail")
async def get_cloudtrail_events(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get recent high-risk CloudTrail events."""
    ts = TimestreamQueryService()
    events = ts.get_resources_by_service(customer.customer_id, "cloudtrail", "24h")
    return {"events": events}


@router.get("/iam")
async def get_iam_summary(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get IAM risk summary."""
    ts = TimestreamQueryService()
    summary = ts.get_resources_by_service(customer.customer_id, "iam")
    return {"summary": summary}


@router.get("/acm")
async def get_acm_certificates(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get ACM certificate inventory with expiry dates."""
    ts = TimestreamQueryService()
    certificates = ts.get_resources_by_service(customer.customer_id, "acm")
    return {"certificates": certificates}


@router.get("/alarms")
async def get_cloudwatch_alarms(
    customer: CustomerContext = Depends(get_current_customer),
    region: Optional[str] = Query(None),
):
    """Get CloudWatch alarm inventory."""
    ts = TimestreamQueryService()
    alarms = ts.get_resources_by_service(customer.customer_id, "cloudwatch_alarms")
    return {"alarms": alarms}
