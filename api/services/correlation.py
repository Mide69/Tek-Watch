"""Cross-service incident correlation.

A compliance check can say "bucket X does not block public access". It cannot
say who did it, when, or what it means. This module joins facts from two
services to answer that: a CloudTrail record of a change to a bucket's access
settings, and the S3 collector's report that the same bucket is now exposed.
Put together they become one incident with a cause, an effect, the UK
regulatory obligations it engages, and ordered steps to fix it.

The same pattern covers audit logging: a StopLogging or DeleteTrail event in
CloudTrail, joined to a trail status of "nothing is logging".

Every incident says whether the cause was actually found. An exposed bucket
with no matching change in the CloudTrail history the agent can see is still
reported, but as uncorrelated: the change predates the history, and the
incident says so rather than guessing at a cause.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.inventory_view import dim, flag, num

S3_ACCESS_EVENTS = frozenset({
    "PutBucketAcl",
    "PutBucketPolicy",
    "DeleteBucketPolicy",
    "PutBucketPublicAccessBlock",
    "DeleteBucketPublicAccessBlock",
})
LOGGING_OFF_EVENTS = frozenset({"StopLogging", "DeleteTrail"})

# CloudTrail history to search for a cause. The agent collects the last 24
# hours on every run and events are kept for the retention period, so this is
# how far back a cause can be found.
CLOUDTRAIL_WINDOW = "30d"
RECENT = timedelta(hours=24)

_S3_IMPACT = [
    {
        "framework": "UK GDPR",
        "reference": "Art. 32 Security of processing",
        "why": "A bucket that does not block public access is not an appropriate technical "
               "measure for personal data.",
    },
    {
        "framework": "UK GDPR",
        "reference": "Art. 33 Notification of a personal data breach",
        "why": "If this bucket holds personal data and was accessed while exposed, the ICO "
               "must be told within 72 hours of you becoming aware, unless the breach is "
               "unlikely to result in a risk to individuals.",
    },
    {
        "framework": "Cyber Essentials",
        "reference": "Secure configuration",
        "why": "Cloud storage must not be left reachable by the public by default.",
    },
]

_LOGGING_IMPACT = [
    {
        "framework": "UK GDPR",
        "reference": "Art. 5(2) Accountability",
        "why": "Without an audit trail you cannot show who accessed or changed personal data.",
    },
    {
        "framework": "ISO 27001:2022",
        "reference": "A.8.15 Logging",
        "why": "Activity logs must be produced, kept and protected.",
    },
]


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _events(cloudtrail: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """High-risk CloudTrail events, flattened and newest first."""
    out = []
    for row in cloudtrail:
        if "high_risk_event" not in (row.get("metrics") or {}):
            continue
        when = _parse_time(dim(row, "event_time")) or _parse_time(row.get("last_seen"))
        out.append({
            "event_id": str(row.get("resource_id") or ""),
            "name": dim(row, "event_name") or str(row.get("resource_name") or ""),
            "user": dim(row, "username") or "unknown",
            "source_ip": dim(row, "source_ip"),
            "resource": dim(row, "resource_name"),
            "region": str(row.get("region") or ""),
            "time": when,
        })
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    out.sort(key=lambda e: e["time"] or epoch, reverse=True)
    return out


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _s3_exposure_incidents(
    buckets: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    latest_change: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if event["name"] in S3_ACCESS_EVENTS and event["resource"]:
            latest_change.setdefault(event["resource"], event)   # newest first

    incidents = []
    for bucket in buckets:
        if flag(bucket, "public_access_blocked") is not False:
            continue
        name = str(bucket.get("resource_name") or bucket.get("resource_id") or "")
        region = dim(bucket, "bucket_region") or str(bucket.get("region") or "")
        cause = latest_change.get(name)

        chain = []
        if cause:
            who = cause["user"] + (f" from {cause['source_ip']}" if cause["source_ip"] else "")
            chain.append({
                "service": "CloudTrail",
                "time": _iso(cause["time"]),
                "detail": f"{cause['name']} on {name} by {who}.",
            })
        chain.append({
            "service": "S3",
            "time": bucket.get("last_seen"),
            "detail": f"{name} no longer has S3 Block Public Access fully enabled.",
        })

        recent = bool(cause and cause["time"] and now - cause["time"] <= RECENT)
        steps = [
            {
                "action": "Block public access on the bucket now.",
                "command": (
                    f"aws s3api put-public-access-block --bucket {name} "
                    "--public-access-block-configuration BlockPublicAcls=true,"
                    "IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
                ),
            },
            {
                "action": "Review the bucket's policy and ACL for grants to everyone.",
                "command": f"aws s3api get-bucket-policy --bucket {name} && aws s3api get-bucket-acl --bucket {name}",
            },
        ]
        if cause:
            steps.append({
                "action": f"Confirm with {cause['user']} that the change was authorised. "
                          "If it was not, rotate their credentials.",
                "command": None,
            })
        steps.extend([
            {
                "action": "Check whether the bucket holds personal data.",
                "command": None,
            },
            {
                "action": "If it does, check access logs for the exposure window and decide "
                          "whether the ICO must be notified within 72 hours.",
                "command": f"aws cloudtrail lookup-events --lookup-attributes AttributeKey=ResourceName,AttributeValue={name}",
            },
        ])

        incidents.append({
            "id": f"s3-exposure:{name}",
            "type": "s3_public_exposure",
            "title": (
                f"{name} was exposed by {cause['name']}" if cause
                else f"{name} does not block public access"
            ),
            "severity": "critical" if recent else "high",
            "correlated": bool(cause),
            "summary": (
                f"{cause['user']} changed the access settings of {name} with {cause['name']}, "
                "and the bucket no longer blocks public access."
                if cause else
                f"{name} does not block public access. No matching change was found in the "
                "CloudTrail history TekWatch can see, so it most likely predates it."
            ),
            "detected_at": _iso(cause["time"]) if cause else bucket.get("last_seen"),
            "affected": [{"service": "S3", "resource": name, "region": region}],
            "chain": chain,
            "regulatory_impact": _S3_IMPACT,
            "remediation": [dict(order=i + 1, **step) for i, step in enumerate(steps)],
        })
    return incidents


def _logging_off_incidents(
    cloudtrail: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    counts = [num(r, "trails_logging_count") for r in cloudtrail]
    counts = [c for c in counts if c is not None]
    if not counts or max(counts) > 0:
        return []
    cause = next((e for e in events if e["name"] in LOGGING_OFF_EVENTS), None)
    if not cause:
        return []   # never logging is a compliance gap (CT-01), not an incident

    trail = cause["resource"] or "the trail"
    who = cause["user"] + (f" from {cause['source_ip']}" if cause["source_ip"] else "")
    return [{
        "id": f"cloudtrail-off:{trail}",
        "type": "audit_logging_disabled",
        "title": f"Audit logging was switched off by {cause['user']}",
        "severity": "critical",
        "correlated": True,
        "summary": f"{cause['name']} on {trail} by {who}, and no CloudTrail trail is logging now.",
        "detected_at": _iso(cause["time"]),
        "affected": [{"service": "CloudTrail", "resource": trail, "region": cause["region"]}],
        "chain": [
            {"service": "CloudTrail", "time": _iso(cause["time"]), "detail": f"{cause['name']} on {trail} by {who}."},
            {"service": "CloudTrail", "time": None, "detail": "No trail is recording activity."},
        ],
        "regulatory_impact": _LOGGING_IMPACT,
        "remediation": [
            {"order": 1, "action": "Turn logging back on.", "command": f"aws cloudtrail start-logging --name {trail}"},
            {"order": 2, "action": f"Confirm with {cause['user']} why logging was stopped.", "command": None},
            {"order": 3, "action": "Restrict cloudtrail:StopLogging and DeleteTrail to a break-glass role.", "command": None},
        ],
    }]


def correlate(inventory: Dict[str, List[Dict[str, Any]]], now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Every correlated incident, most severe and most recent first."""
    now = now or datetime.now(timezone.utc)
    cloudtrail = inventory.get("cloudtrail", [])
    events = _events(cloudtrail)
    incidents = (
        _s3_exposure_incidents(inventory.get("s3", []), events, now)
        + _logging_off_incidents(cloudtrail, events)
    )
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    incidents.sort(key=lambda i: (rank.get(i["severity"], 9), not i["correlated"], i["id"]))
    return incidents


def load_inventory(ts: Any, customer_id: str) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "s3": ts.get_service_inventory(customer_id, "s3", "24h"),
        "cloudtrail": ts.get_service_inventory(customer_id, "cloudtrail", CLOUDTRAIL_WINDOW),
    }
