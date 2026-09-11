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

FCA PS21/3 is deliberately absent. Operational resilience under PS21/3 is about
important business services, impact tolerances and scenario testing, none of
which can be judged from AWS configuration. Claiming a score for it would be
exactly the kind of invented figure this module exists to remove.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.inventory_view import dim, flag, num, text

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"
NOT_APPLICABLE = "not_applicable"

FRAMEWORKS: List[Dict[str, str]] = [
    {"id": "uk_gdpr", "name": "UK GDPR"},
    {"id": "cyber_essentials", "name": "Cyber Essentials"},
    {"id": "iso27001", "name": "ISO 27001:2022"},
]

DISCLAIMER = (
    "These are automated checks of the AWS technical controls TekWatch can see. "
    "They help you gather evidence and spot gaps. They are not a certification, "
    "an audit, or legal advice."
)

# Services the checks read, and how far back to look for their latest state.
# A day rather than an hour: a compliance view should show the last known
# state through a short agent gap instead of flipping everything to unknown.
INVENTORY_SERVICES = ("s3", "iam", "acm", "guardduty", "cloudtrail")
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
        frameworks.append({
            "id": fw["id"],
            "name": fw["name"],
            "score": round(100 * passed / evaluated) if evaluated else None,
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "total": len(relevant),
        })

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
