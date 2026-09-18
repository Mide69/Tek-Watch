"""UK compliance control checks, evaluated from what the agent actually collects.

The Security page used to show GDPR 84%, Cyber Essentials 76%, FCA 91% and
ISO 27001 68% for every customer. Those numbers were constants in the
dashboard: nothing computed them, and a real account saw 0% across the board.

This module replaces them with real checks. Each control reads facts the agent
already reports (S3 public access and encryption, IAM MFA and key age,
certificate expiry, GuardDuty, CloudTrail logging), decides pass / fail /
unknown, and names the specific resources that failed and how to fix them.
Each control is mapped to the clauses it supports in UK GDPR, Cyber Essentials
and ISO 27001:2022.

Two rules keep it honest:

* A fact the agent did not collect is "unknown", never a pass. Unknown and
  not-applicable controls are left out of a framework's score rather than
  quietly counted as met.
* A score is the share of *evaluated technical controls* that passed. It is
  not a certification, and the payload says so.

FCA PS21/3 is handled differently from the others, and on purpose. Operational
resilience under PS21/3 is about identifying important business services,
setting impact tolerances and testing against severe but plausible scenarios.
None of that can be read from an AWS account, and a PS21/3 "score" from a
configuration scan would be exactly the kind of invented figure this module
exists to remove.

What an AWS account can show is the technical half of the evidence a firm needs
when it maps the resources behind an important business service: whether the
database can survive losing an availability zone, whether it can be restored,
whether the front door is spread across zones, and whether anyone is watching.
Those checks are here, grouped under PS21/3 and labelled technical evidence
only, with the framework carrying a scope note saying what is out of scope.
The firm still has to do the rest.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.inventory_view import dim, dim_num, flag, num, text

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"
NOT_APPLICABLE = "not_applicable"

FRAMEWORKS: List[Dict[str, Any]] = [
    {"id": "uk_gdpr", "name": "UK GDPR"},
    {
        "id": "cyber_essentials",
        "name": "Cyber Essentials v3.3",
        "scope": "cloud_controls_only",
        "scope_note": (
            "The cloud side only. From an AWS account TekWatch can evidence firewalls and "
            "internet gateways, secure configuration, user access control, and the cloud half of "
            "security update management, such as functions left on retired runtimes. Malware "
            "protection, and patching on the laptops and phones your people use, are not visible "
            "to TekWatch and are not assessed here. Version 3.3 applies to assessments from "
            "27 April 2026 and puts cloud services firmly in scope."
        ),
    },
    {"id": "iso27001", "name": "ISO 27001:2022"},
    {
        "id": "fca_ps21_3",
        "name": "FCA PS21/3 operational resilience",
        "scope": "technical_evidence_only",
        "scope_note": (
            "Technical evidence only. These checks show whether the AWS resources behind a "
            "service can survive a failure and be restored, which supports the resource "
            "mapping a firm must do under PS21/3. Identifying important business services, "
            "setting impact tolerances and scenario testing are governance work that cannot "
            "be read from AWS configuration, and are not assessed here."
        ),
    },
]

DISCLAIMER = (
    "These are automated checks of the AWS technical controls TekWatch can see. "
    "They help you gather evidence and spot gaps. They are not a certification, "
    "an audit, or legal advice."
)

# Services the checks read, and how far back to look for their latest state.
# A day rather than an hour: a compliance view should show the last known
# state through a short agent gap instead of flipping everything to unknown.
INVENTORY_SERVICES = (
    "s3", "iam", "acm", "guardduty", "cloudtrail", "rds", "elb", "cloudwatch_alarms",
    "lambda", "dynamodb", "sqs", "sns", "eks", "elasticache", "cloudfront",
    "config", "security_hub",
)
INVENTORY_WINDOW = "24h"

Inventory = Dict[str, List[Dict[str, Any]]]


@dataclass
class ControlResult:
    id: str
    title: str
    severity: str
    status: str
    detail: str
    remediation: str
    references: List[Dict[str, str]]
    findings: List[Dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ref(framework: str, reference: str) -> Dict[str, str]:
    return {"framework": framework, "reference": reference}


def bool_metric(resource: Optional[Dict[str, Any]], key: str) -> Optional[bool]:
    """A metric that may arrive as "true"/"false" text or as 1/0.

    root_mfa_active is sent as the string "true" or "false", which lands in
    the events table as text. Reading it with num() always returned None, so
    root MFA showed as unknown for every customer.
    """
    if not resource:
        return None
    raw = text(resource, key, "")
    if raw.strip().lower() in ("true", "1", "1.0", "yes"):
        return True
    if raw.strip().lower() in ("false", "0", "0.0", "no"):
        return False
    return None


def _name(resource: Dict[str, Any]) -> str:
    return str(resource.get("resource_name") or resource.get("resource_id") or "unknown")


# ── S3 ────────────────────────────────────────────────────────────────────────

def _bucket_flag_control(
    inv: Inventory,
    key: str,
    *,
    cid: str,
    title: str,
    severity: str,
    fail_detail: str,
    remediation: str,
    references: List[Dict[str, str]],
) -> ControlResult:
    buckets = inv.get("s3", [])
    base = dict(id=cid, title=title, severity=severity, remediation=remediation, references=references)
    if not buckets:
        return ControlResult(status=NOT_APPLICABLE, detail="No S3 buckets reported.", **base)

    failing = [b for b in buckets if flag(b, key) is False]
    unknown = [b for b in buckets if flag(b, key) is None]
    findings = [{"resource": _name(b), "detail": fail_detail} for b in failing]

    if failing:
        detail = f"{len(failing)} of {len(buckets)} buckets fail this check."
        return ControlResult(status=FAIL, detail=detail, findings=findings, **base)
    if unknown:
        detail = (
            f"Could not read this setting for {len(unknown)} of {len(buckets)} buckets. "
            "The agent may lack permission, or has not reported them yet."
        )
        return ControlResult(status=UNKNOWN, detail=detail, **base)
    return ControlResult(status=PASS, detail=f"All {len(buckets)} buckets pass.", **base)


def _s3_public_access(inv: Inventory) -> ControlResult:
    return _bucket_flag_control(
        inv, "public_access_blocked",
        cid="S3-01",
        title="S3 buckets block public access",
        severity="high",
        fail_detail="S3 Block Public Access is not fully enabled on this bucket.",
        remediation=(
            "Turn on all four S3 Block Public Access settings for each bucket, or for "
            "the whole account: aws s3api put-public-access-block --bucket <name> "
            "--public-access-block-configuration BlockPublicAcls=true,"
            "IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(b) confidentiality of processing systems"),
            _ref("cyber_essentials", "Secure configuration"),
            _ref("iso27001", "A.8.3 Information access restriction"),
        ],
    )


def _s3_encryption(inv: Inventory) -> ControlResult:
    return _bucket_flag_control(
        inv, "encryption_enabled",
        cid="S3-02",
        title="S3 buckets encrypt data at rest",
        severity="medium",
        fail_detail="Default encryption is not configured on this bucket.",
        remediation=(
            "Enable default encryption (SSE-S3 or SSE-KMS): aws s3api "
            "put-bucket-encryption --bucket <name> --server-side-encryption-configuration "
            "'{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}'"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(a) encryption of personal data"),
            _ref("iso27001", "A.8.24 Use of cryptography"),
        ],
    )


def _s3_versioning(inv: Inventory) -> ControlResult:
    return _bucket_flag_control(
        inv, "versioning_enabled",
        cid="S3-03",
        title="S3 buckets keep previous versions",
        severity="low",
        fail_detail="Versioning is off, so an overwrite or deletion cannot be undone.",
        remediation=(
            "Enable versioning on buckets that hold data you would need to restore: "
            "aws s3api put-bucket-versioning --bucket <name> "
            "--versioning-configuration Status=Enabled"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(c) ability to restore availability and access"),
            _ref("iso27001", "A.8.13 Information backup"),
            _ref("fca_ps21_3", "Ability to recover data supporting an important business service"),
        ],
    )


# ── IAM ───────────────────────────────────────────────────────────────────────

_IAM_ACCESS_REFS = [
    _ref("uk_gdpr", "Art. 32(1)(b) confidentiality of processing systems"),
    _ref("cyber_essentials", "User access control"),
    _ref("iso27001", "A.8.5 Secure authentication"),
]


def _iam_summary(inv: Inventory) -> Optional[Dict[str, Any]]:
    iam = inv.get("iam", [])
    return iam[0] if iam else None


def _iam_user_mfa(inv: Inventory) -> ControlResult:
    base = dict(
        id="IAM-01", title="Every IAM user with a password uses MFA", severity="high",
        remediation=(
            "Assign an MFA device to each IAM user that can sign in to the console, "
            "and add an IAM policy that denies access without MFA."
        ),
        references=_IAM_ACCESS_REFS,
    )
    count = num(_iam_summary(inv) or {}, "users_without_mfa_count")
    if count is None:
        return ControlResult(status=UNKNOWN, detail="MFA status has not been reported yet.", **base)
    if count > 0:
        n = int(count)
        return ControlResult(
            status=FAIL,
            detail=f"{n} IAM user{'s' if n != 1 else ''} can sign in without MFA.",
            findings=[{"resource": "IAM users", "detail": f"{n} without MFA"}],
            **base,
        )
    return ControlResult(status=PASS, detail="All console users have MFA.", **base)


def _iam_root_mfa(inv: Inventory) -> ControlResult:
    base = dict(
        id="IAM-02", title="The root account uses MFA", severity="critical",
        remediation=(
            "Sign in as the root user, open Security credentials, and assign an MFA "
            "device. Then stop using the root account for day-to-day work."
        ),
        references=_IAM_ACCESS_REFS,
    )
    active = bool_metric(_iam_summary(inv), "root_mfa_active")
    if active is None:
        return ControlResult(status=UNKNOWN, detail="Root MFA status has not been reported yet.", **base)
    if not active:
        return ControlResult(
            status=FAIL, detail="The root account has no MFA device.",
            findings=[{"resource": "Root account", "detail": "No MFA"}], **base,
        )
    return ControlResult(status=PASS, detail="The root account has MFA.", **base)


def _iam_old_keys(inv: Inventory) -> ControlResult:
    base = dict(
        id="IAM-03", title="No access keys older than 90 days", severity="medium",
        remediation=(
            "Rotate each old key: create a new key, update whatever uses it, then "
            "deactivate and delete the old one. Prefer IAM roles over long-lived keys."
        ),
        references=[
            _ref("cyber_essentials", "User access control"),
            _ref("iso27001", "A.5.17 Authentication information"),
        ],
    )
    count = num(_iam_summary(inv) or {}, "access_keys_older_than_90_days")
    if count is None:
        return ControlResult(status=UNKNOWN, detail="Access key age has not been reported yet.", **base)
    if count > 0:
        n = int(count)
        return ControlResult(
            status=FAIL, detail=f"{n} access key{'s are' if n != 1 else ' is'} older than 90 days.",
            findings=[{"resource": "IAM access keys", "detail": f"{n} older than 90 days"}], **base,
        )
    return ControlResult(status=PASS, detail="No access key is older than 90 days.", **base)


# ── ACM ───────────────────────────────────────────────────────────────────────

def _acm_expiry(inv: Inventory) -> ControlResult:
    base = dict(
        id="ACM-01", title="TLS certificates in use are not about to expire", severity="medium",
        remediation=(
            "Renew or replace certificates before they expire. Amazon-issued certificates "
            "renew automatically only while their DNS validation records stay in place."
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(a) encryption of personal data in transit"),
            _ref("iso27001", "A.8.24 Use of cryptography"),
        ],
    )
    # Only issued certificates protect anything. One stuck in validation or
    # timed out reports an expiry of -1 and would otherwise read as "expired".
    issued = [c for c in inv.get("acm", []) if dim(c, "status").upper() == "ISSUED"]
    if not issued:
        return ControlResult(status=NOT_APPLICABLE, detail="No issued certificates reported.", **base)

    failing, unknown = [], []
    for cert in issued:
        days = num(cert, "days_until_expiry")
        if days is None:
            unknown.append(cert)
        elif days < 30:
            failing.append((cert, int(days)))

    if failing:
        return ControlResult(
            status=FAIL,
            detail=f"{len(failing)} of {len(issued)} certificates expire within 30 days.",
            findings=[
                {"resource": dim(c, "domain") or _name(c), "detail": f"Expires in {d} days"}
                for c, d in failing
            ],
            **base,
        )
    if unknown:
        return ControlResult(status=UNKNOWN, detail="Expiry dates have not been reported for every certificate.", **base)
    return ControlResult(status=PASS, detail=f"All {len(issued)} certificates have 30+ days left.", **base)


# ── GuardDuty ─────────────────────────────────────────────────────────────────

def _guardduty_detectors(inv: Inventory) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(enabled, disabled) per-region GuardDuty records."""
    enabled, disabled = [], []
    for r in inv.get("guardduty", []):
        metrics = r.get("metrics") or {}
        status = num(r, "detector_enabled")
        if status is None and any(k.startswith("findings_") and k.endswith("_count") for k in metrics):
            status = 1   # an agent older than detector_enabled only sent counts for live detectors
        if status == 1:
            enabled.append(r)
        elif status == 0:
            disabled.append(r)
    return enabled, disabled


def _guardduty_enabled(inv: Inventory) -> ControlResult:
    base = dict(
        id="GD-01", title="GuardDuty threat detection is switched on", severity="high",
        remediation=(
            "Enable GuardDuty in every region you run workloads in: "
            "aws guardduty create-detector --enable --region <region>"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(d) testing and assessing security measures"),
            _ref("iso27001", "A.8.16 Monitoring activities"),
        ],
    )
    enabled, disabled = _guardduty_detectors(inv)
    if enabled:
        regions = sorted({str(r.get("region") or "") for r in enabled} - {""})
        return ControlResult(status=PASS, detail=f"Enabled in {', '.join(regions) or 'at least one region'}.", **base)
    if disabled:
        return ControlResult(
            status=FAIL, detail="GuardDuty is not enabled in any region.",
            findings=[{"resource": "GuardDuty", "detail": "No detector in any region"}], **base,
        )
    return ControlResult(status=UNKNOWN, detail="GuardDuty status has not been reported yet.", **base)


def _guardduty_open_findings(inv: Inventory) -> ControlResult:
    base = dict(
        id="GD-02", title="No open high or critical GuardDuty findings", severity="high",
        remediation=(
            "Investigate each high or critical finding on the Security page, contain the "
            "affected resource, and archive the finding once it is resolved."
        ),
        references=[
            _ref("uk_gdpr", "Art. 33 assessing and notifying personal data breaches"),
            _ref("iso27001", "A.5.26 Response to information security incidents"),
        ],
    )
    enabled, _ = _guardduty_detectors(inv)
    if not enabled:
        return ControlResult(status=NOT_APPLICABLE, detail="GuardDuty is not reporting findings.", **base)
    serious = 0
    for r in enabled:
        serious += int((num(r, "findings_high_count") or 0) + (num(r, "findings_critical_count") or 0))
    if serious:
        return ControlResult(
            status=FAIL, detail=f"{serious} high or critical finding{'s' if serious != 1 else ''} open.",
            findings=[{"resource": "GuardDuty", "detail": f"{serious} high/critical findings"}], **base,
        )
    return ControlResult(status=PASS, detail="No high or critical findings open.", **base)


# ── CloudTrail ────────────────────────────────────────────────────────────────

def _cloudtrail_logging(inv: Inventory) -> ControlResult:
    base = dict(
        id="CT-01", title="A CloudTrail trail is recording activity", severity="medium",
        remediation=(
            "Create a multi-region trail that logs to a dedicated S3 bucket: "
            "aws cloudtrail create-trail --name org-trail --s3-bucket-name <bucket> "
            "--is-multi-region-trail, then aws cloudtrail start-logging --name org-trail"
        ),
        references=[
            _ref("uk_gdpr", "Art. 5(2) accountability"),
            _ref("iso27001", "A.8.15 Logging"),
        ],
    )
    counts = [num(r, "trails_logging_count") for r in inv.get("cloudtrail", [])]
    counts = [c for c in counts if c is not None]
    if not counts:
        return ControlResult(status=UNKNOWN, detail="Trail status has not been reported yet.", **base)
    if max(counts) > 0:
        return ControlResult(status=PASS, detail="At least one trail is logging.", **base)
    return ControlResult(
        status=FAIL, detail="No CloudTrail trail is logging.",
        findings=[{"resource": "CloudTrail", "detail": "No logging trail"}], **base,
    )


# ── Operational resilience (FCA PS21/3 technical evidence) ────────────────────

def _rds_instances(inv: Inventory) -> List[Dict[str, Any]]:
    """Inventory rows for databases, one per instance."""
    return [r for r in inv.get("rds", []) if dim(r, "engine")]


def _rds_multi_az(inv: Inventory) -> ControlResult:
    base = dict(
        id="RES-01", title="Databases run in more than one availability zone", severity="high",
        remediation=(
            "Turn on Multi-AZ for production databases: aws rds modify-db-instance "
            "--db-instance-identifier <id> --multi-az --apply-immediately. AWS keeps a "
            "standby in a second zone and fails over to it."
        ),
        references=[
            _ref("fca_ps21_3", "Remaining within impact tolerance when a data centre is lost"),
            _ref("iso27001", "A.8.14 Redundancy of information processing facilities"),
        ],
    )
    databases = _rds_instances(inv)
    if not databases:
        return ControlResult(status=NOT_APPLICABLE, detail="No databases reported.", **base)

    single = [d for d in databases if flag(d, "multi_az") is False]
    unknown = [d for d in databases if flag(d, "multi_az") is None]
    if single:
        return ControlResult(
            status=FAIL,
            detail=f"{len(single)} of {len(databases)} databases run in a single zone.",
            findings=[{"resource": _name(d), "detail": "Single availability zone"} for d in single],
            **base,
        )
    if unknown:
        return ControlResult(status=UNKNOWN, detail="Zone configuration has not been reported for every database.", **base)
    return ControlResult(status=PASS, detail=f"All {len(databases)} databases span two zones.", **base)


def _rds_backups(inv: Inventory) -> ControlResult:
    base = dict(
        id="RES-02", title="Databases keep automated backups", severity="critical",
        remediation=(
            "Set a retention period of at least 7 days: aws rds modify-db-instance "
            "--db-instance-identifier <id> --backup-retention-period 7 --apply-immediately"
        ),
        references=[
            _ref("fca_ps21_3", "Ability to restore an important business service after an incident"),
            _ref("uk_gdpr", "Art. 32(1)(c) ability to restore availability and access"),
            _ref("iso27001", "A.8.13 Information backup"),
        ],
    )
    databases = _rds_instances(inv)
    if not databases:
        return ControlResult(status=NOT_APPLICABLE, detail="No databases reported.", **base)

    retention = [(d, dim_num(d, "backup_retention_days")) for d in databases]
    none_kept = [(d, r) for d, r in retention if r is not None and r <= 0]
    unknown = [d for d, r in retention if r is None]
    if none_kept:
        return ControlResult(
            status=FAIL,
            detail=f"{len(none_kept)} of {len(databases)} databases keep no automated backups.",
            findings=[{"resource": _name(d), "detail": "Backup retention is 0 days"} for d, _ in none_kept],
            **base,
        )
    if unknown:
        return ControlResult(status=UNKNOWN, detail="Backup retention has not been reported for every database.", **base)
    shortest = min(int(r) for _, r in retention if r is not None)
    return ControlResult(status=PASS, detail=f"Every database keeps at least {shortest} days of backups.", **base)


def _elb_zone_spread(inv: Inventory) -> ControlResult:
    base = dict(
        id="RES-03", title="Load balancers span at least two availability zones", severity="medium",
        remediation=(
            "Attach a subnet from a second zone: aws elbv2 set-subnets --load-balancer-arn "
            "<arn> --subnets <subnet-a> <subnet-b>"
        ),
        references=[
            _ref("fca_ps21_3", "Resilience of the entry point to an important business service"),
            _ref("iso27001", "A.8.14 Redundancy of information processing facilities"),
        ],
    )
    balancers = [r for r in inv.get("elb", []) if dim(r, "type")]
    if not balancers:
        return ControlResult(status=NOT_APPLICABLE, detail="No load balancers reported.", **base)

    counts = [(b, dim_num(b, "availability_zone_count")) for b in balancers]
    single = [(b, c) for b, c in counts if c is not None and c < 2]
    unknown = [b for b, c in counts if c is None]
    if single:
        return ControlResult(
            status=FAIL,
            detail=f"{len(single)} of {len(balancers)} load balancers sit in one zone.",
            findings=[{"resource": _name(b), "detail": f"{int(c)} availability zone"} for b, c in single],
            **base,
        )
    if unknown:
        return ControlResult(status=UNKNOWN, detail="Zone spread has not been reported for every load balancer.", **base)
    return ControlResult(status=PASS, detail=f"All {len(balancers)} load balancers span two or more zones.", **base)


def _alarms_exist(inv: Inventory) -> ControlResult:
    base = dict(
        id="RES-04", title="CloudWatch alarms are configured", severity="medium",
        remediation=(
            "Create alarms for the things that would breach your impact tolerance first: "
            "database CPU and storage, load balancer 5xx responses, and queue age."
        ),
        references=[
            _ref("fca_ps21_3", "Detecting an incident in time to stay within impact tolerance"),
            _ref("iso27001", "A.8.16 Monitoring activities"),
        ],
    )
    alarms = inv.get("cloudwatch_alarms", [])
    if alarms:
        return ControlResult(status=PASS, detail=f"{len(alarms)} alarms configured.", **base)
    # An empty list means one of two different things: the agent looked and
    # found no alarms, or nothing has been reported at all. Treating silence as
    # a failure would fail a customer for our own blind spot, so only call it a
    # failure when the agent is plainly reporting other services.
    if any(rows for service, rows in inv.items() if service != "cloudwatch_alarms"):
        return ControlResult(
            status=FAIL,
            detail="No CloudWatch alarms are configured.",
            findings=[{"resource": "CloudWatch", "detail": "No alarms found"}],
            **base,
        )
    return ControlResult(status=UNKNOWN, detail="Alarms have not been reported yet.", **base)


# ── Data stores beyond S3 ─────────────────────────────────────────────────────

def _flag_control(
    inv: Inventory,
    service: str,
    key: str,
    *,
    cid: str,
    title: str,
    severity: str,
    noun: str,
    fail_detail: str,
    remediation: str,
    references: List[Dict[str, str]],
    identify=None,
    want: bool = True,
) -> ControlResult:
    """Pass when every resource of a kind has a boolean dimension set the right way.

    One shape for eight checks. Each still reports which resources failed and
    keeps the same rule: a flag the agent never sent is unknown, never a pass.
    """
    base = dict(id=cid, title=title, severity=severity, remediation=remediation, references=references)
    resources = [r for r in inv.get(service, []) if (identify is None or identify(r))]
    if not resources:
        return ControlResult(status=NOT_APPLICABLE, detail=f"No {noun} reported.", **base)

    failing = [r for r in resources if flag(r, key) is (not want)]
    unknown = [r for r in resources if flag(r, key) is None]
    if failing:
        return ControlResult(
            status=FAIL,
            detail=f"{len(failing)} of {len(resources)} {noun} fail this check.",
            findings=[{"resource": _name(r), "detail": fail_detail} for r in failing],
            **base,
        )
    if unknown:
        return ControlResult(
            status=UNKNOWN,
            detail=f"This setting has not been reported for {len(unknown)} of {len(resources)} {noun}.",
            **base,
        )
    return ControlResult(status=PASS, detail=f"All {len(resources)} {noun} pass.", **base)


def _rds_not_public(inv: Inventory) -> ControlResult:
    return _flag_control(
        inv, "rds", "publicly_accessible",
        cid="RDS-01",
        title="Databases are not reachable from the internet",
        severity="critical",
        noun="databases",
        fail_detail="This database has a public endpoint",
        remediation=(
            "Turn off public access: aws rds modify-db-instance --db-instance-identifier "
            "<id> --no-publicly-accessible --apply-immediately, and reach it through your VPC."
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(b) confidentiality of processing systems"),
            _ref("cyber_essentials", "Firewalls and internet gateways"),
            _ref("iso27001", "A.8.20 Network security"),
        ],
        identify=lambda r: bool(dim(r, "engine")),
        want=False,
    )


def _dynamodb_recovery(inv: Inventory) -> ControlResult:
    return _flag_control(
        inv, "dynamodb", "point_in_time_recovery",
        cid="DDB-01",
        title="DynamoDB tables can be restored to a point in time",
        severity="high",
        noun="tables",
        fail_detail="Point-in-time recovery is off",
        remediation=(
            "Switch it on: aws dynamodb update-continuous-backups --table-name <name> "
            "--point-in-time-recovery-specification PointInTimeRecoveryEnabled=true"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(c) ability to restore availability and access"),
            _ref("iso27001", "A.8.13 Information backup"),
            _ref("fca_ps21_3", "Ability to recover data supporting an important business service"),
        ],
    )


def _sqs_encryption(inv: Inventory) -> ControlResult:
    return _flag_control(
        inv, "sqs", "encryption_enabled",
        cid="SQS-01",
        title="Queues encrypt the messages they hold",
        severity="medium",
        noun="queues",
        fail_detail="Server-side encryption is off",
        remediation=(
            "Turn on SQS-managed encryption: aws sqs set-queue-attributes --queue-url <url> "
            "--attributes SqsManagedSseEnabled=true"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(a) encryption of personal data"),
            _ref("iso27001", "A.8.24 Use of cryptography"),
        ],
    )


def _sns_encryption(inv: Inventory) -> ControlResult:
    return _flag_control(
        inv, "sns", "encryption_enabled",
        cid="SNS-01",
        title="Topics encrypt the messages they carry",
        severity="medium",
        noun="topics",
        fail_detail="Server-side encryption is off",
        remediation=(
            "Attach a KMS key: aws sns set-topic-attributes --topic-arn <arn> "
            "--attribute-name KmsMasterKeyId --attribute-value alias/aws/sns"
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(a) encryption of personal data"),
            _ref("iso27001", "A.8.24 Use of cryptography"),
        ],
    )


def _elasticache_encryption(inv: Inventory) -> ControlResult:
    return _flag_control(
        inv, "elasticache", "at_rest_encryption",
        cid="EC-01",
        title="Caches encrypt what they store",
        severity="medium",
        noun="cache clusters",
        fail_detail="Encryption at rest is off",
        remediation=(
            "Encryption at rest cannot be turned on in place. Create a replacement cluster "
            "with --at-rest-encryption-enabled and move traffic to it."
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(a) encryption of personal data"),
            _ref("iso27001", "A.8.24 Use of cryptography"),
        ],
    )


def _eks_private_endpoint(inv: Inventory) -> ControlResult:
    return _flag_control(
        inv, "eks", "endpoint_public_access",
        cid="EKS-01",
        title="Kubernetes API endpoints are not open to the whole internet",
        severity="high",
        noun="clusters",
        fail_detail="The Kubernetes API is reachable from the internet",
        remediation=(
            "Restrict it: aws eks update-cluster-config --name <cluster> "
            "--resources-vpc-config endpointPublicAccess=false,endpointPrivateAccess=true, "
            "or keep public access but set publicAccessCidrs to your own addresses."
        ),
        references=[
            _ref("cyber_essentials", "Firewalls and internet gateways"),
            _ref("iso27001", "A.8.20 Network security"),
        ],
        identify=lambda r: bool(text(r, "cluster_status", "")),
        want=False,
    )


# ── Delivery and posture ──────────────────────────────────────────────────────

_INSECURE_VIEWER_POLICIES = {"allow-all"}


def _cloudfront_https(inv: Inventory) -> ControlResult:
    base = dict(
        id="CF-01", title="CloudFront serves over HTTPS only", severity="medium",
        remediation=(
            "Set the viewer protocol policy to redirect-to-https or https-only on the "
            "default behaviour of each distribution."
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(a) encryption of personal data in transit"),
            _ref("cyber_essentials", "Secure configuration"),
            _ref("iso27001", "A.8.24 Use of cryptography"),
        ],
    )
    distributions = [r for r in inv.get("cloudfront", []) if dim(r, "domain")]
    if not distributions:
        return ControlResult(status=NOT_APPLICABLE, detail="No CloudFront distributions reported.", **base)

    failing = [d for d in distributions if dim(d, "viewer_protocol_policy") in _INSECURE_VIEWER_POLICIES]
    unknown = [d for d in distributions if not dim(d, "viewer_protocol_policy")]
    if failing:
        return ControlResult(
            status=FAIL,
            detail=f"{len(failing)} of {len(distributions)} distributions allow plain HTTP.",
            findings=[{"resource": _name(d), "detail": "Viewer protocol policy is allow-all"} for d in failing],
            **base,
        )
    if unknown:
        return ControlResult(status=UNKNOWN, detail="The viewer protocol policy has not been reported for every distribution.", **base)
    return ControlResult(status=PASS, detail=f"All {len(distributions)} distributions require HTTPS.", **base)


def _lambda_supported_runtimes(inv: Inventory) -> ControlResult:
    base = dict(
        id="LAM-01", title="Functions run supported language runtimes", severity="medium",
        remediation=(
            "Move each function to a supported runtime and redeploy. AWS stops applying "
            "security patches to a runtime once it reaches end of support."
        ),
        references=[
            _ref("cyber_essentials", "Security update management"),
            _ref("uk_gdpr", "Art. 32(1)(b) ongoing security of processing systems"),
            _ref("iso27001", "A.8.8 Management of technical vulnerabilities"),
        ],
    )
    functions = [r for r in inv.get("lambda", []) if dim(r, "runtime")]
    if not functions:
        return ControlResult(status=NOT_APPLICABLE, detail="No Lambda functions reported.", **base)

    failing = [f for f in functions if _is_deprecated_runtime(dim(f, "runtime"))]
    if failing:
        return ControlResult(
            status=FAIL,
            detail=f"{len(failing)} of {len(functions)} functions run a retired runtime.",
            findings=[{"resource": _name(f), "detail": f"Runtime {dim(f, 'runtime')} is no longer supported"} for f in failing],
            **base,
        )
    return ControlResult(status=PASS, detail=f"All {len(functions)} functions run supported runtimes.", **base)


# Runtimes AWS has already retired. Deliberately a list of what is known to be
# dead rather than a list of what is alive: a new runtime we have not heard of
# must not be reported as a failure.
DEPRECATED_RUNTIME_PREFIXES = (
    "python2.7", "python3.6", "python3.7", "python3.8",
    "nodejs", "nodejs4.3", "nodejs6.10", "nodejs8.10", "nodejs10.x", "nodejs12.x",
    "nodejs14.x", "nodejs16.x",
    "ruby2.5", "ruby2.7", "dotnetcore2.1", "dotnetcore3.1", "dotnet5.0", "dotnet6",
    "java8", "go1.x",
)


def _is_deprecated_runtime(runtime: str) -> bool:
    name = (runtime or "").strip().lower()
    return name in DEPRECATED_RUNTIME_PREFIXES


def _config_rules_passing(inv: Inventory) -> ControlResult:
    base = dict(
        id="CFG-01", title="AWS Config rules are passing", severity="medium",
        remediation=(
            "Open AWS Config, read each non-compliant rule, and fix the resources it names. "
            "Config rules are your own policy, so a failure here is a rule you set yourself."
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(d) testing and assessing security measures"),
            _ref("iso27001", "A.8.9 Configuration management"),
        ],
    )
    rows = inv.get("config", [])
    non_compliant = [num(r, "non_compliant_rules_count") for r in rows]
    non_compliant = [int(c) for c in non_compliant if c is not None]
    if not non_compliant:
        return ControlResult(status=UNKNOWN, detail="AWS Config has not reported yet.", **base)
    total = sum(non_compliant)
    if total:
        return ControlResult(
            status=FAIL,
            detail=f"{total} Config rule{'s' if total != 1 else ''} are failing.",
            findings=[{"resource": "AWS Config", "detail": f"{total} non-compliant rules"}],
            **base,
        )
    return ControlResult(status=PASS, detail="No Config rule is failing.", **base)


def _security_hub_findings(inv: Inventory) -> ControlResult:
    base = dict(
        id="SH-01", title="No open critical Security Hub findings", severity="high",
        remediation=(
            "Work through the critical findings in Security Hub, fix the resource each one "
            "names, and resolve the finding."
        ),
        references=[
            _ref("uk_gdpr", "Art. 32(1)(d) testing and assessing security measures"),
            _ref("iso27001", "A.5.26 Response to information security incidents"),
        ],
    )
    rows = inv.get("security_hub", [])
    counts = [num(r, "findings_critical_count") for r in rows]
    counts = [int(c) for c in counts if c is not None]
    if not counts:
        return ControlResult(status=NOT_APPLICABLE, detail="Security Hub is not reporting findings.", **base)
    total = sum(counts)
    if total:
        return ControlResult(
            status=FAIL,
            detail=f"{total} critical finding{'s' if total != 1 else ''} open.",
            findings=[{"resource": "Security Hub", "detail": f"{total} critical findings"}],
            **base,
        )
    return ControlResult(status=PASS, detail="No critical findings open.", **base)


CONTROLS: List[Callable[[Inventory], ControlResult]] = [
    _s3_public_access,
    _s3_encryption,
    _s3_versioning,
    _iam_user_mfa,
    _iam_root_mfa,
    _iam_old_keys,
    _acm_expiry,
    _guardduty_enabled,
    _guardduty_open_findings,
    _cloudtrail_logging,
    _rds_multi_az,
    _rds_backups,
    _elb_zone_spread,
    _alarms_exist,
    _rds_not_public,
    _dynamodb_recovery,
    _sqs_encryption,
    _sns_encryption,
    _elasticache_encryption,
    _eks_private_endpoint,
    _cloudfront_https,
    _lambda_supported_runtimes,
    _config_rules_passing,
    _security_hub_findings,
]


def evaluate(inventory: Inventory, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run every control and score each framework from the results."""
    now = now or datetime.now(timezone.utc)
    results = [control(inventory) for control in CONTROLS]

    frameworks = []
    for fw in FRAMEWORKS:
        relevant = [r for r in results if any(ref["framework"] == fw["id"] for ref in r.references)]
        passed = sum(1 for r in relevant if r.status == PASS)
        failed = sum(1 for r in relevant if r.status == FAIL)
        unknown = sum(1 for r in relevant if r.status == UNKNOWN)
        evaluated = passed + failed
        entry = {
            "id": fw["id"],
            "name": fw["name"],
            "score": round(100 * passed / evaluated) if evaluated else None,
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "total": len(relevant),
        }
        # PS21/3 carries a scope note, because a score against part of a
        # regime must not be read as a score against the regime.
        if fw.get("scope"):
            entry["scope"] = fw["scope"]
            entry["scope_note"] = fw["scope_note"]
        frameworks.append(entry)

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    status_rank = {FAIL: 0, UNKNOWN: 1, PASS: 2, NOT_APPLICABLE: 3}
    results.sort(key=lambda r: (status_rank.get(r.status, 9), severity_rank.get(r.severity, 9)))

    return {
        "evaluated_at": now.isoformat(),
        "frameworks": frameworks,
        "controls": [r.as_dict() for r in results],
        "disclaimer": DISCLAIMER,
    }


def load_inventory(ts: Any, customer_id: str, window: str = INVENTORY_WINDOW) -> Inventory:
    """The latest folded state of every service the checks read."""
    return {svc: ts.get_service_inventory(customer_id, svc, window) for svc in INVENTORY_SERVICES}
