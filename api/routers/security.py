"""Security router — GuardDuty, IAM, ACM, alarms, compliance, incidents, evidence."""
import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response

from auth.dependencies import CustomerContext, get_current_customer
from services import compliance, correlation, evidence, exposure
from services.dynamodb import DynamoDBService
from services.inventory_view import dim, num, text, wants_region_filter
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)
router = APIRouter()


def _guardduty_severity(score: Optional[float]) -> str:
    """GuardDuty's numeric severity as the label the page shows.

    Same bands the collector uses when it counts findings by severity.
    """
    if score is None:
        return "UNKNOWN"
    if score >= 9:
        return "CRITICAL"
    if score >= 7:
        return "HIGH"
    if score >= 4:
        return "MEDIUM"
    return "LOW"


@router.get("/guardduty")
async def get_guardduty_findings(
    customer: CustomerContext = Depends(get_current_customer),
    severity: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
):
    """Get GuardDuty findings.

    The collector reports each finding as a `finding_severity` score with
    `type`, `resource_type` and `created_at` dimensions, plus one per-region
    detector row carrying counts. This read `finding_type`, `severity` and
    `description` dimensions that no collector sends, and listed the detector
    rows as findings, so a real account saw one "UNKNOWN" finding per region
    and none of the real ones' details.
    """
    ts = TimestreamQueryService()
    findings = []
    for f in ts.get_service_inventory(customer.customer_id, "guardduty"):
        if "finding_severity" not in (f.get("metrics") or {}):
            continue
        findings.append({
            "finding_id": f["resource_id"],
            "type": dim(f, "type") or f["resource_name"],
            "severity": _guardduty_severity(num(f, "finding_severity")),
            "region": f.get("region") or "",
            "resource": dim(f, "resource_type"),
            "description": f.get("resource_name") or "",
            "updated_at": dim(f, "created_at") or f.get("last_seen"),
            "count": 1,
        })
    if severity:
        wanted = severity.upper()
        findings = [f for f in findings if str(f["severity"]).upper() == wanted]
    if wants_region_filter(region):
        findings = [f for f in findings if f["region"] == region]
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
        # The collector also emits per-region rollups (high_risk_events_24h,
        # trails_logging_count). Those are numbers about the region, not
        # events, and listing them as one put a row named
        # "cloudtrail-eu-west-2" in among the audit events.
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
    # Sent as the text "true"/"false", so it lands in the events table as a
    # string. num() on it was always None, and root MFA read as "not measured"
    # for every customer even though the agent had measured it.
    root_mfa = compliance.bool_metric(iam, "root_mfa_active")

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
            "root_mfa_enabled": root_mfa,
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
    """Get CloudWatch alarm inventory.

    This was never migrated off get_resources_by_service — the raw-row method
    every other endpoint here moved away from. It queried a 5-minute window
    (the same class of bug that zeroed the overview) and returned rows shaped
    {resource_id, resource_name, metric_name, value, time}, none of which are
    the fields this page reads (alarm_name, state, namespace, metric,
    threshold). It rendered because the mismatch didn't crash — a.alarm_name
    on a row with no such key is just undefined — it silently showed a blank
    row per alarm instead of failing.
    """
    ts = TimestreamQueryService()
    alarms = [
        {
            "alarm_name": a["resource_name"],
            "state": text(a, "alarm_state", "UNKNOWN"),
            "namespace": dim(a, "namespace"),
            "metric": dim(a, "metric_name"),
            "threshold": dim(a, "threshold"),
            # The collector reports the alarm's state, not the metric reading
            # that tripped it — CloudWatch's DescribeAlarms doesn't return
            # that value either, only GetMetricData does, which this
            # collector doesn't call. Not collected, so not guessed.
            "value": None,
            "region": a.get("region") or "",
            "last_seen": a.get("last_seen"),
        }
        for a in ts.get_service_inventory(customer.customer_id, "cloudwatch_alarms")
    ]
    if wants_region_filter(region):
        alarms = [a for a in alarms if a["region"] == region]
    return {"alarms": alarms}


@router.get("/compliance")
async def get_compliance(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Automated compliance checks, evaluated from the customer's own data.

    Replaces four fixed percentages the dashboard used to show every customer.
    See services/compliance.py for what is checked and how it is scored.
    """
    ts = TimestreamQueryService()
    report = compliance.evaluate(compliance.load_inventory(ts, customer.customer_id))
    # What a failing control could cost, from published sources only. See
    # services/exposure.py for why this is three separate figures and not one.
    report["exposure"] = exposure.estimate(report)
    return report


@router.get("/incidents")
async def get_incidents(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Security incidents built by joining CloudTrail changes to current state.

    See services/correlation.py.
    """
    ts = TimestreamQueryService()
    return {"incidents": correlation.correlate(correlation.load_inventory(ts, customer.customer_id))}


@router.get("/evidence")
async def get_evidence(
    limit: int = Query(50, ge=1, le=200),
    customer: CustomerContext = Depends(get_current_customer),
):
    """The compliance evidence log: what was assessed, what changed, and when.

    A compliance page shows today. This shows the history, which is what a
    Cyber Essentials assessor or an ICO caseworker asks for.
    """
    db = DynamoDBService()
    entries = db.list_evidence(customer.customer_id, limit=limit)
    head = db.evidence_head(customer.customer_id)
    return {
        "entries": entries,
        "total_recorded": head.get("seq", 0),
        "statement": evidence.STATEMENT,
    }


@router.get("/evidence/verify")
async def verify_evidence(
    customer: CustomerContext = Depends(get_current_customer),
):
    """Recompute the whole chain and report whether it is intact.

    The check is done from the stored bodies, not from a stored answer, so it
    fails if any entry has been altered since it was written.
    """
    db = DynamoDBService()
    return evidence.verify(db.all_evidence(customer.customer_id))


@router.get("/evidence/export")
async def export_evidence(
    customer: CustomerContext = Depends(get_current_customer),
):
    """The log as a CSV file, with the hashes, for an audit pack."""
    entries = DynamoDBService().all_evidence(customer.customer_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["seq", "recorded_at", "kind", "summary", "hash", "prev_hash"])
    for entry in entries:
        writer.writerow([
            entry.get("seq"),
            entry.get("recorded_at"),
            entry.get("kind"),
            entry.get("summary"),
            entry.get("hash"),
            entry.get("prev_hash"),
        ])
    filename = f"tekwatch-compliance-evidence-{customer.customer_id}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
