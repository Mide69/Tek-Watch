"""The compliance evidence record: append-only, hash-chained, checkable.

A compliance page tells you what is wrong today. It cannot tell you what was
wrong in March, when you fixed it, or prove to anyone that the answer has not
been edited since. That is the thing a Cyber Essentials assessor or an ICO
caseworker actually asks for, and it is what this module keeps.

Every entry carries the hash of the entry before it, so the log can be checked
from end to end: change one stored entry and every hash after it stops
matching. Nobody has to trust our word for it, because verify() recomputes the
whole chain from the stored bodies.

Chaining alone proves nobody edited an entry afterwards. It cannot prove when
an entry was made, because every time in the chain is one we wrote. So once a
day the head of the chain is sent to an independent RFC 3161 timestamping
authority and its signed token is recorded as an anchor (see
services/timestamping.py). From then on the log carries proof of age that does
not depend on trusting us.

What is still true and worth saying out loud: an anchor proves the chain
existed at that time, not that our records are correct, and a log with no
anchors yet says so rather than borrowing the claim.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

GENESIS = "0" * 64

SNAPSHOT = "snapshot"       # the compliance position at a point in time
RESOLVED = "resolved"       # a control that was failing now passes
REGRESSED = "regressed"     # a control that was passing now fails
ANCHOR = "anchor"           # an independent timestamp over the chain so far

STATEMENT = (
    "Each entry is chained to the one before it with SHA-256, so any later edit to a "
    "stored entry breaks every hash after it. Once a day the head of the chain is sent to "
    "an independent timestamping authority, which returns a signed RFC 3161 token proving "
    "the chain existed at that time. You can check a token yourself with openssl, without "
    "TekWatch."
)

# Said instead when a log has no anchors yet, so nothing claims proof it lacks.
STATEMENT_WITHOUT_ANCHORS = (
    "Each entry is chained to the one before it with SHA-256, so any later edit to a "
    "stored entry breaks every hash after it. This log has not been anchored to an "
    "independent timestamp yet; anchoring runs daily."
)


def statement_for(entries: List[Dict[str, Any]]) -> str:
    """The wording this particular log has earned."""
    return STATEMENT if any(e.get("kind") == ANCHOR for e in entries) else STATEMENT_WITHOUT_ANCHORS


def canonical(body: Dict[str, Any]) -> str:
    """One byte-for-byte form of a body, so a hash is reproducible."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def entry_hash(prev_hash: str, seq: int, recorded_at: str, kind: str, body: Dict[str, Any]) -> str:
    material = "|".join([prev_hash, str(seq), recorded_at, kind, canonical(body)])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_entry(
    *,
    prev_hash: str,
    seq: int,
    kind: str,
    summary: str,
    body: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    recorded_at = (now or datetime.now(timezone.utc)).isoformat()
    return {
        "seq": seq,
        "recorded_at": recorded_at,
        "kind": kind,
        "summary": summary,
        "body": body,
        "prev_hash": prev_hash,
        "hash": entry_hash(prev_hash, seq, recorded_at, kind, body),
    }


def anchor_body(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """What is kept from a timestamp token, so it can be checked later."""
    return {
        "anchored_hash": stamp.get("anchored_hash"),
        "authority": stamp.get("authority"),
        "requested_at": stamp.get("requested_at"),
        "nonce": stamp.get("nonce"),
        "token_sha256": stamp.get("token_sha256"),
        "token_b64": stamp.get("token_b64"),
        "verify": stamp.get("verify"),
    }


def verify(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Recompute the chain. Returns where it breaks, if it breaks."""
    ordered = sorted(entries, key=lambda e: int(e.get("seq", 0)))
    anchors = [e for e in ordered if e.get("kind") == ANCHOR]
    prev = GENESIS
    for entry in ordered:
        expected = entry_hash(
            prev,
            int(entry.get("seq", 0)),
            str(entry.get("recorded_at", "")),
            str(entry.get("kind", "")),
            entry.get("body") or {},
        )
        if entry.get("prev_hash") != prev or entry.get("hash") != expected:
            return {
                "intact": False,
                "entries_checked": len(ordered),
                "broken_at": entry.get("seq"),
                "anchors": len(anchors),
                "last_anchored_at": _last_anchor_time(anchors),
                "statement": statement_for(ordered),
            }
        prev = str(entry["hash"])
    return {
        "intact": True,
        "entries_checked": len(ordered),
        "broken_at": None,
        "anchors": len(anchors),
        "last_anchored_at": _last_anchor_time(anchors),
        "statement": statement_for(ordered),
    }


def _last_anchor_time(anchors: List[Dict[str, Any]]) -> Optional[str]:
    if not anchors:
        return None
    return str(anchors[-1].get("recorded_at"))


def _statuses(report: Dict[str, Any]) -> Dict[str, str]:
    return {str(c.get("id")): str(c.get("status")) for c in report.get("controls", [])}


def snapshot_body(report: Dict[str, Any], exposure: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What is worth keeping forever out of one evaluation.

    The full report carries every resource name that failed and can be large;
    the record keeps the verdicts, the scores and the exposure headline, which
    is what an assessor asks to see.
    """
    body: Dict[str, Any] = {
        "evaluated_at": report.get("evaluated_at"),
        "frameworks": [
            {k: fw.get(k) for k in ("id", "name", "score", "passed", "failed", "unknown", "total")}
            for fw in report.get("frameworks", [])
        ],
        "controls": [
            {
                "id": c.get("id"),
                "title": c.get("title"),
                "status": c.get("status"),
                "severity": c.get("severity"),
                "failing_resources": len(c.get("findings") or []),
            }
            for c in report.get("controls", [])
        ],
    }
    if exposure:
        body["exposure"] = {
            "failing_controls": exposure.get("failing_controls"),
            "direct_cost": exposure.get("direct_cost", {}).get("display"),
            "comparable_enforcement": exposure.get("comparable_enforcement", {}).get("display"),
        }
    return body


def transitions(
    previous: Optional[Dict[str, Any]], report: Dict[str, Any]
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """(kind, summary, body) for each control that changed verdict.

    This is the "verify" half of the workflow. A customer fixes something, the
    agent reports the new state, the control is re-evaluated on the next pass,
    and the change is recorded with the time it was seen. Nobody has to press a
    button to claim it is fixed: the record follows the evidence.
    """
    if not previous:
        return []
    before = {str(c.get("id")): c for c in previous.get("controls", [])}
    out: List[Tuple[str, str, Dict[str, Any]]] = []
    for control in report.get("controls", []):
        cid = str(control.get("id"))
        was = before.get(cid)
        if not was:
            continue
        old, new = str(was.get("status")), str(control.get("status"))
        if old == new:
            continue
        body = {
            "control_id": cid,
            "title": control.get("title"),
            "severity": control.get("severity"),
            "from": old,
            "to": new,
            "detail": control.get("detail"),
            "observed_at": report.get("evaluated_at"),
        }
        if old == "fail" and new == "pass":
            out.append((RESOLVED, f"{cid} now passes: {control.get('title')}", body))
        elif old == "pass" and new == "fail":
            out.append((REGRESSED, f"{cid} started failing: {control.get('title')}", body))
    return out


def changed_since(previous: Optional[Dict[str, Any]], report: Dict[str, Any]) -> bool:
    """True when any control's verdict differs from the last recorded snapshot."""
    if not previous:
        return True
    return _statuses(previous) != _statuses(report)
