"""Dates the customer has to meet, worked out from their own account.

The plan lists a "Regulatory Calendar" among the things TekWatch combines.
There was none. This is it, and it is built on the same rule as everything
else here: a date appears only when something real sets it.

Three kinds of entry:

* deadline  — a clock already running, such as the 72 hours Article 33 gives
              you to tell the ICO about a breach, counted from when TekWatch
              first saw the exposure
* expiry    — something that stops working on a date AWS told us, such as a
              TLS certificate
* renewal   — a yearly obligation whose date only the customer knows, such as
              a Cyber Essentials certificate. Until they enter it, the entry
              says the date is not set rather than inventing one

Nothing here is a reminder we made up. If the account has nothing due, the
calendar is honestly empty.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.inventory_view import dim, num

DEADLINE = "deadline"
EXPIRY = "expiry"
RENEWAL = "renewal"

# Article 33(1): the ICO must be told within 72 hours of becoming aware of a
# personal data breach, unless it is unlikely to risk people's rights.
ICO_NOTIFICATION_HOURS = 72
ICO_ARTICLE_33 = (
    "https://ico.org.uk/for-organisations/report-a-breach/personal-data-breach/"
)
# The dates a customer has to tell us, because nothing in AWS knows them.
SELF_DECLARED = {
    "cyber_essentials_expires_at": {
        "title": "Cyber Essentials certification expires",
        "why": "Certification lasts twelve months. Most buyers who ask for it check the date.",
        "framework": "Cyber Essentials",
    },
    "ico_fee_due_at": {
        "title": "ICO data protection fee due",
        "why": "Most organisations that process personal data must pay the ICO every year.",
        "framework": "UK GDPR",
    },
}


@dataclass
class Entry:
    id: str
    kind: str
    title: str
    due_at: Optional[str]
    days_remaining: Optional[int]
    overdue: bool
    urgency: str
    detail: str
    framework: str
    source: Optional[str] = None
    action: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _urgency(days: Optional[int], overdue: bool) -> str:
    if overdue:
        return "overdue"
    if days is None:
        return "unknown"
    if days <= 1:
        return "critical"
    if days <= 14:
        return "soon"
    return "scheduled"


def _entry(
    *, id: str, kind: str, title: str, due: Optional[datetime], now: datetime,
    detail: str, framework: str, source: Optional[str] = None, action: Optional[str] = None,
) -> Entry:
    days = None if due is None else (due - now).days
    overdue = bool(due and due < now)
    return Entry(
        id=id, kind=kind, title=title,
        due_at=due.isoformat() if due else None,
        days_remaining=days, overdue=overdue,
        urgency=_urgency(days, overdue),
        detail=detail, framework=framework, source=source, action=action,
    )


def _breach_clocks(incidents: List[Dict[str, Any]], now: datetime) -> List[Entry]:
    """The 72-hour clock on anything that exposed data.

    Counted from when TekWatch first saw the exposure, which is the earliest
    defensible reading of "became aware" and the one that gives the customer
    the least comfortable, most useful answer.
    """
    entries: List[Entry] = []
    for incident in incidents:
        if incident.get("type") not in ("s3_public_exposure", "database_publicly_reachable"):
            continue
        detected = _parse(incident.get("detected_at"))
        if not detected:
            continue
        due = detected + timedelta(hours=ICO_NOTIFICATION_HOURS)
        resource = (incident.get("affected") or [{}])[0].get("resource", "a resource")
        entries.append(_entry(
            id=f"ico-72h:{incident.get('id')}",
            kind=DEADLINE,
            title=f"Decide whether the ICO must be told about {resource}",
            due=due, now=now,
            detail=(
                "Article 33 gives you 72 hours from becoming aware of a personal data breach "
                "to tell the ICO, unless it is unlikely to risk people's rights. If no personal "
                "data was exposed, record that decision and why."
            ),
            framework="UK GDPR",
            source=ICO_ARTICLE_33,
            action="Check what was in it, decide, and write the decision down either way.",
        ))
    return entries


def _certificate_expiries(inventory: Dict[str, List[Dict[str, Any]]], now: datetime) -> List[Entry]:
    entries: List[Entry] = []
    for cert in inventory.get("acm", []):
        if dim(cert, "status") and dim(cert, "status") != "ISSUED":
            continue
        days = num(cert, "days_until_expiry")
        if days is None:
            continue
        domain = dim(cert, "domain") or str(cert.get("resource_name") or "certificate")
        entries.append(_entry(
            id=f"cert-expiry:{cert.get('resource_id')}",
            kind=EXPIRY,
            title=f"TLS certificate for {domain} expires",
            due=now + timedelta(days=int(days)), now=now,
            detail=(
                "An expired certificate stops the service and breaks encryption in transit. "
                "Certificates issued by ACM renew themselves only while the validation records "
                "are still in place."
            ),
            framework="UK GDPR",
            action="Confirm the DNS validation records still exist so ACM can renew it.",
        ))
    return entries


def _self_declared(profile: Dict[str, Any], now: datetime) -> List[Entry]:
    entries: List[Entry] = []
    for field, meta in SELF_DECLARED.items():
        due = _parse(profile.get(field))
        entries.append(_entry(
            id=f"renewal:{field}",
            kind=RENEWAL,
            title=meta["title"],
            due=due, now=now,
            detail=meta["why"] if due else f"{meta['why']} Add your date and TekWatch will track it.",
            framework=meta["framework"],
            action=None if due else "Set the date on your profile.",
        ))
    return entries


_URGENCY_ORDER = {"overdue": 0, "critical": 1, "soon": 2, "scheduled": 3, "unknown": 4}


def build(
    inventory: Dict[str, List[Dict[str, Any]]],
    incidents: List[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Everything with a date on it, soonest and most pressing first."""
    now = now or datetime.now(timezone.utc)
    entries = (
        _breach_clocks(incidents, now)
        + _certificate_expiries(inventory, now)
        + _self_declared(profile or {}, now)
    )
    entries.sort(key=lambda e: (
        _URGENCY_ORDER.get(e.urgency, 9),
        e.days_remaining if e.days_remaining is not None else 10_000,
    ))
    return {
        "generated_at": now.isoformat(),
        "entries": [e.as_dict() for e in entries],
        "overdue": sum(1 for e in entries if e.overdue),
        "due_within_14_days": sum(
            1 for e in entries
            if not e.overdue and e.days_remaining is not None and e.days_remaining <= 14
        ),
        "awaiting_your_date": sum(1 for e in entries if e.kind == RENEWAL and e.due_at is None),
    }
