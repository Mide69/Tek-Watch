"""Cross-service incident correlation.

A compliance check can say "bucket X does not block public access". It cannot
say who did it, when, or what it means. This module joins facts from two
services to answer that: a CloudTrail record of a change to a bucket's access
settings, and the S3 collector's report that the same bucket is now exposed.
Put together they become one incident with a cause, an effect, the UK
regulatory obligations it engages, and ordered steps to fix it.

The same pattern covers three more: a database given a public endpoint, a
console sign-in as root while root has no MFA, and audit logging switched off
(a StopLogging or DeleteTrail event joined to a trail status of "nothing is
logging").

Each incident also carries an operational impact: what it means for the
business, in plain English, worked out from what the agent collected, such as
how much data sits in the exposed bucket or how big the database is.

Every incident says whether the cause was actually found. An exposed bucket
with no matching change in the CloudTrail history the agent can see is still
reported, but as uncorrelated: the change predates the history, and the
incident says so rather than guessing at a cause.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.compliance import bool_metric
from services import topology
from services.inventory_view import dim, flag, num

S3_ACCESS_EVENTS = frozenset({
    "PutBucketAcl",
    "PutBucketPolicy",
    "DeleteBucketPolicy",
    "PutBucketPublicAccessBlock",
    "DeleteBucketPublicAccessBlock",
})
LOGGING_OFF_EVENTS = frozenset({"StopLogging", "DeleteTrail"})
DB_EXPOSURE_EVENTS = frozenset({
    "ModifyDBInstance",
    "CreateDBInstance",
    "AuthorizeSecurityGroupIngress",
})
ROOT_LOGIN_EVENTS = frozenset({"ConsoleLogin"})
_ROOT_USERNAMES = {"root", "account root", "aws root"}

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


_DB_IMPACT = [
    {
        "framework": "UK GDPR",
        "reference": "Art. 32 Security of processing",
        "why": "A database holding personal data should not be reachable from the public "
               "internet; only the security group and the password stand in the way.",
    },
    {
        "framework": "Cyber Essentials",
        "reference": "Firewalls and internet gateways",
        "why": "Services must not be exposed to the internet unless there is a documented "
               "business need.",
    },
    {
        "framework": "ISO 27001:2022",
        "reference": "A.8.20 Networks security",
        "why": "Networks must be managed and controlled to protect the systems on them.",
    },
]

_ROOT_IMPACT = [
    {
        "framework": "UK GDPR",
        "reference": "Art. 32(1)(b) Confidentiality of processing systems",
        "why": "The root user can read, change or delete everything in the account, "
               "including personal data, with one password.",
    },
    {
        "framework": "Cyber Essentials",
        "reference": "User access control",
        "why": "Accounts with administrative access must use multi-factor authentication.",
    },
    {
        "framework": "ISO 27001:2022",
        "reference": "A.8.5 Secure authentication",
        "why": "Privileged access requires strong authentication.",
    },
]


def _bytes_human(value: float) -> str:
    """Bytes as something a non-engineer can read."""
    size = float(value)
    for unit in ("bytes", "KB", "MB", "GB"):
        if abs(size) < 1024:
            return f"{size:,.0f} {unit}" if unit == "bytes" else f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} TB"


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

        objects = num(bucket, "number_of_objects")
        size = num(bucket, "bucket_size_bytes")
        points = []
        if objects is not None:
            points.append(f"The bucket holds {int(objects):,} objects.")
        if size is not None:
            points.append(f"That is {_bytes_human(size)} of data.")
        if objects is None and size is None:
            points.append(
                "How much data is in this bucket has not been reported yet, so the amount "
                "at stake is unknown."
            )
        points.append(
            "Block Public Access is what stops a policy or ACL from granting access to "
            "everyone. With it off, such a grant now takes effect."
        )
        operational = {
            "headline": f"Public access is no longer prevented on {name}",
            "points": points,
        }

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
            "operational_impact": operational,
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
        "operational_impact": {
            "headline": "You cannot reconstruct what happens in this account",
            "points": [
                "New activity is not being recorded anywhere.",
                "An investigation, including deciding whether personal data was touched, "
                "has no record to work from.",
                "Log files written before it was switched off are unaffected.",
            ],
        },
        "remediation": [
            {"order": 1, "action": "Turn logging back on.", "command": f"aws cloudtrail start-logging --name {trail}"},
            {"order": 2, "action": f"Confirm with {cause['user']} why logging was stopped.", "command": None},
            {"order": 3, "action": "Restrict cloudtrail:StopLogging and DeleteTrail to a break-glass role.", "command": None},
        ],
    }]


def _public_database_incidents(
    databases: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    now: datetime,
) -> List[Dict[str, Any]]:
    """A database with a public endpoint, and whoever gave it one."""
    latest_change: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if event["name"] in DB_EXPOSURE_EVENTS and event["resource"]:
            latest_change.setdefault(event["resource"], event)   # newest first

    incidents = []
    for db in databases:
        if flag(db, "publicly_accessible") is not True:
            continue
        name = str(db.get("resource_name") or db.get("resource_id") or "")
        region = str(db.get("region") or "")
        engine = dim(db, "engine") or "database"
        storage = dim(db, "allocated_storage_gb")
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
            "service": "RDS",
            "time": db.get("last_seen"),
            "detail": f"{name} has a public endpoint.",
        })

        points = [
            f"This is a {engine} instance" + (f" with {storage} GB of storage." if storage else "."),
            "Anyone on the internet can reach the endpoint; only the security group and the "
            "database password stand in the way.",
        ]
        if dim(db, "multi_az").lower() == "true":
            points.append("It is a multi-AZ instance, so it is likely to be production.")

        recent = bool(cause and cause["time"] and now - cause["time"] <= RECENT)
        steps = [
            {
                "action": "Turn off public access unless there is a documented reason for it.",
                "command": f"aws rds modify-db-instance --db-instance-identifier {name} "
                           "--no-publicly-accessible --apply-immediately",
            },
            {
                "action": "Check which addresses the security group allows in. Anything open "
                          "to 0.0.0.0/0 on the database port should go.",
                "command": f"aws rds describe-db-instances --db-instance-identifier {name} "
                           "--query 'DBInstances[0].VpcSecurityGroups'",
            },
            {
                "action": "Rotate the database password if it has been exposed for any length "
                          "of time.",
                "command": None,
            },
            {
                "action": "Check whether this database holds personal data, and if it does, "
                          "decide whether the ICO must be told.",
                "command": None,
            },
        ]

        incidents.append({
            "id": f"rds-public:{name}",
            "type": "database_publicly_reachable",
            "title": (
                f"{name} was made reachable from the internet by {cause['name']}" if cause
                else f"{name} is reachable from the internet"
            ),
            "severity": "critical" if recent else "high",
            "correlated": bool(cause),
            "summary": (
                f"{cause['user']} ran {cause['name']} on {name}, and the database now has a "
                "public endpoint."
                if cause else
                f"{name} has a public endpoint. No matching change was found in the CloudTrail "
                "history TekWatch can see, so it most likely predates it."
            ),
            "detected_at": _iso(cause["time"]) if cause else db.get("last_seen"),
            "affected": [{"service": "RDS", "resource": name, "region": region}],
            "chain": chain,
            "regulatory_impact": _DB_IMPACT,
            "operational_impact": {
                "headline": f"{name} can be reached from outside your network",
                "points": points,
            },
            "remediation": [dict(order=i + 1, **step) for i, step in enumerate(steps)],
        })
    return incidents


def _root_login_incidents(
    iam: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Someone signed in as root while the root account has no MFA.

    Root without MFA on its own is a failed compliance check (IAM-02). It
    becomes an incident when the account is actually being used that way.
    """
    if not iam:
        return []
    if bool_metric(iam[0], "root_mfa_active") is not False:
        return []

    login = next(
        (e for e in events
         if e["name"] in ROOT_LOGIN_EVENTS and e["user"].strip().lower() in _ROOT_USERNAMES),
        None,
    )
    if not login:
        return []

    who = "the root user" + (f" from {login['source_ip']}" if login["source_ip"] else "")
    return [{
        "id": "root-login-no-mfa",
        "type": "root_login_without_mfa",
        "title": "The root account signed in and has no MFA",
        "severity": "critical",
        "correlated": True,
        "summary": f"A console sign-in by {who}, and the root account has no MFA device. "
                   "A stolen password alone is enough to take over the account.",
        "detected_at": _iso(login["time"]),
        "affected": [{"service": "IAM", "resource": "root account", "region": login["region"]}],
        "chain": [
            {"service": "CloudTrail", "time": _iso(login["time"]),
             "detail": f"ConsoleLogin by {who}."},
            {"service": "IAM", "time": iam[0].get("last_seen"),
             "detail": "The root account has no MFA device."},
        ],
        "regulatory_impact": _ROOT_IMPACT,
        "operational_impact": {
            "headline": "The account's most powerful credentials have no second factor",
            "points": [
                "Root can delete every resource, the backups and the audit trail.",
                "It cannot be restricted by IAM policy the way other users can.",
                "Day-to-day work should use an IAM user or role, not root.",
            ],
        },
        "remediation": [
            {"order": 1, "action": "Add an MFA device to the root account: sign in as root, "
                                   "open Security credentials, and assign one.", "command": None},
            {"order": 2, "action": "Confirm the sign-in was you. If it was not, treat it as a "
                                   "breach: change the root password and review recent activity.",
             "command": None},
            {"order": 3, "action": "Stop using root for daily work. Create an IAM user or role "
                                   "with only the access it needs.", "command": None},
        ],
    }]


# Which service an incident's affected resource belongs to, in the graph's
# vocabulary. The affected list is written for a reader ("S3"), the graph is
# keyed the way the agent reports ("s3").
_GRAPH_SERVICE = {"S3": "s3", "RDS": "rds", "EC2": "ec2", "LAMBDA": "lambda"}


def _attach_service_impact(incidents: List[Dict[str, Any]], graph: topology.Graph) -> None:
    """Say what else each incident reaches, using the customer's own graph.

    An incident about one bucket is really an incident about everything that
    bucket is wired to. Until this existed the product could name the resource
    that changed and nothing else, which is the gap between an alert and an
    impact assessment.
    """
    for incident in incidents:
        found = {"serves": [], "reachable_from": [], "runs_in": [], "total": 0, "summary": ""}
        for affected in incident.get("affected", []):
            service = _GRAPH_SERVICE.get(str(affected.get("service", "")).upper())
            if not service:
                continue
            result = topology.impact(graph, topology.key_for(service, str(affected.get("resource"))))
            if not result.get("resource"):
                continue
            for field in ("serves", "reachable_from", "runs_in"):
                found[field].extend(result[field])
            found["total"] += result["total"]
            found["summary"] = topology.summarise(result)
        incident["service_impact"] = found


def correlate(
    inventory: Dict[str, List[Dict[str, Any]]],
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Every correlated incident, most severe and most recent first."""
    now = now or datetime.now(timezone.utc)
    cloudtrail = inventory.get("cloudtrail", [])
    events = _events(cloudtrail)
    incidents = (
        _s3_exposure_incidents(inventory.get("s3", []), events, now)
        + _public_database_incidents(inventory.get("rds", []), events, now)
        + _root_login_incidents(inventory.get("iam", []), events)
        + _logging_off_incidents(cloudtrail, events)
    )
    _attach_service_impact(incidents, topology.build(inventory))
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    incidents.sort(key=lambda i: (rank.get(i["severity"], 9), not i["correlated"], i["id"]))
    return incidents


def load_inventory(ts: Any, customer_id: str) -> Dict[str, List[Dict[str, Any]]]:
    services = {"s3", "rds", "iam", *topology.TOPOLOGY_SERVICES}
    inventory = {svc: ts.get_service_inventory(customer_id, svc, "24h") for svc in sorted(services)}
    inventory["cloudtrail"] = ts.get_service_inventory(customer_id, "cloudtrail", CLOUDTRAIL_WINDOW)
    return inventory
