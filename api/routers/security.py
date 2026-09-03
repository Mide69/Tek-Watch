"""Security router — GuardDuty, IAM, ACM, CloudWatch Alarms."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CustomerContext, get_current_customer
from services.inventory_view import dim, num, text
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
    findings = [
        {
            "finding_id": f["resource_id"],
            "type": dim(f, "finding_type") or f["resource_name"],
            "severity": dim(f, "severity") or "UNKNOWN",
            "region": f.get("region") or "",
            "resource": dim(f, "resource_name") or dim(f, "resource"),
            "description": dim(f, "description"),
            "updated_at": dim(f, "updated_at") or f.get("last_seen"),
            "count": num(f, "finding_count") or 1,
        }
        for f in ts.get_service_inventory(customer.customer_id, "guardduty")
    ]
    if severity:
        wanted = severity.upper()
        findings = [f for f in findings if str(f["severity"]).upper() == wanted]
    return {"findings": findings}


@router.get("/cloudtrail")
async def get_cloudtrail_events(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get recent high-risk CloudTrail events."""
    ts = TimestreamQueryService()
    events = [
        {
            "event_id": e["resource_id"],
            "event_name": dim(e, "event_name") or e["resource_name"],
            "username": dim(e, "username"),
            "source_ip": dim(e, "source_ip"),
            "resource": dim(e, "resource_name"),
            "event_time": dim(e, "event_time") or e.get("last_seen"),
            "region": e.get("region") or "",
        }
        for e in ts.get_service_inventory(customer.customer_id, "cloudtrail", "24h")
        # The collector also emits a per-region rollup count under
        # high_risk_events_24h. That is a number about the region, not an
        # event, and listing it as one put a row named "cloudtrail-eu-west-2"
        # in among the audit events.
        if "high_risk_event" in (e.get("metrics") or {})
    ]
    events.sort(key=lambda e: str(e.get("event_time") or ""), reverse=True)
    return {"events": events}


@router.get("/iam")
async def get_iam_summary(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get IAM risk summary.

    The IAM collector reports one resource carrying several metrics, so this
    folds to a single object rather than a list. It returned the raw rows,
    which the page read as `iam.users_total` — always undefined.
    """
    ts = TimestreamQueryService()
    resources = ts.get_service_inventory(customer.customer_id, "iam")
    iam = resources[0] if resources else {}

    users_total = num(iam, "total_users")
    without_mfa = num(iam, "users_without_mfa_count")
    root_mfa = num(iam, "root_mfa_active")

    return {
        "summary": {
            "users_total": users_total,
            "users_without_mfa": without_mfa,
            "users_with_mfa": (
                users_total - without_mfa
                if users_total is not None and without_mfa is not None
                else None
            ),
            "roles_total": num(iam, "total_roles"),
            "old_access_keys": num(iam, "access_keys_older_than_90_days"),
            "root_mfa_enabled": None if root_mfa is None else bool(root_mfa),
            # Not collected by any agent collector yet. None keeps the page
            # honest about that rather than showing a reassuring zero for a
            # risk nobody has actually checked.
            "root_access_keys": None,
            "overprivileged_roles": None,
            "unused_credentials_90d": None,
            "policies_inline": None,
            "policies_customer_managed": None,
            "last_root_activity": None,
            "last_seen": iam.get("last_seen"),
        }
    }


@router.get("/acm")
async def get_acm_certificates(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Get ACM certificate inventory with expiry dates."""
    ts = TimestreamQueryService()
    certificates = [
        {
            "certificate_arn": c["resource_id"],
            "domain": dim(c, "domain") or c["resource_name"],
            "status": dim(c, "status") or text(c, "certificate_status", "UNKNOWN"),
            "type": dim(c, "type"),
            "region": c.get("region") or "",
            "expires_at": dim(c, "expiry_date"),
            "days_to_expiry": num(c, "days_until_expiry"),
            "in_use": None,
            "auto_renew": None,
        }
        for c in ts.get_service_inventory(customer.customer_id, "acm")
    ]
    certificates.sort(
        key=lambda c: (c["days_to_expiry"] is None, c["days_to_expiry"] or 0)
    )
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
