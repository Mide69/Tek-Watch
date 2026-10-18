"""Hash-chained assessment evidence with optional RFC 3161 responses.

Hash links expose changes relative to a trusted head. A complete rewrite cannot
be detected without an independently retained head or verified external anchor.
Timestamp responses require signature and trust-chain verification; neither a
hash chain nor a timestamp proves the accuracy of the underlying observations.
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
    "SHA-256 links allow internal chain consistency to be checked. This log contains "
    "RFC 3161 responses: verify their signatures and target hashes independently with "
    "openssl and a trusted authority certificate. Only a successful external anchor or "
    "separately trusted chain head detects a fully rewritten history. Neither establishes "
    "that the original observation or assessment was correct."
)

# Said instead when a log has no anchors yet, so nothing claims proof it lacks.
STATEMENT_WITHOUT_ANCHORS = (
    "SHA-256 links permit internal consistency checks. This log has not been anchored "
    "to an independent timestamp yet; anchoring runs daily on a best-effort basis. "
    "Without a separately trusted head, rewritten history cannot be excluded."
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


def verify(entries: List[Dict[str, Any]], expected_head: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Recompute the chain. Returns where it breaks, if it breaks."""
    ordered = sorted(entries, key=lambda e: int(e.get("seq", 0)))
    anchors = [e for e in ordered if e.get("kind") == ANCHOR]
    prev = GENESIS
    sequence = 1
    for entry in ordered:
        expected = entry_hash(
            prev,
            int(entry.get("seq", 0)),
            str(entry.get("recorded_at", "")),
            str(entry.get("kind", "")),
            entry.get("body") or {},
        )
        if int(entry.get("seq", 0)) != sequence or entry.get("prev_hash") != prev or entry.get("hash") != expected:
            return {
                "intact": False,
                "entries_checked": len(ordered),
                "broken_at": entry.get("seq"),
                "anchors": len(anchors),
                "last_anchored_at": _last_anchor_time(anchors),
                "statement": statement_for(ordered),
            }
        prev = str(entry["hash"])
        sequence += 1
    complete = expected_head is not None and (
        int(expected_head.get("seq", 0)) == len(ordered)
        and str(expected_head.get("hash", GENESIS)) == prev
    )
    return {
        "intact": complete if expected_head is not None else True,
        "complete": complete,
        "verification_scope": "hash_links_and_sequence; timestamp signatures require independent verification",
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
        "pack": report.get("pack"),
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
                "observed_at": c.get("observed_at"),
                "rule_version": c.get("rule_version"),
                "observations": c.get("observations", []),
                "references": c.get("references", []),
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
            "observed_at": control.get("observed_at"),
            "assessed_at": report.get("evaluated_at"),
            "rule_version": control.get("rule_version"),
            "pack": report.get("pack"),
        }
        if old == "fail" and new == "pass":
            # A changed verdict is not proof of a fix without a newer observation.
            try:
                observed = datetime.fromisoformat(str(control.get("observed_at")).replace("Z", "+00:00"))
                prior = datetime.fromisoformat(str(previous.get("evaluated_at")).replace("Z", "+00:00"))
                if observed.tzinfo is None or prior.tzinfo is None or observed <= prior:
                    continue
            except (ValueError, TypeError):
                continue
            out.append((RESOLVED, f"{cid} now passes: {control.get('title')}", body))
        elif old == "pass" and new == "fail":
            out.append((REGRESSED, f"{cid} started failing: {control.get('title')}", body))
    return out


def changed_since(previous: Optional[Dict[str, Any]], report: Dict[str, Any]) -> bool:
    """True when any control's verdict differs from the last recorded snapshot."""
    if not previous:
        return True
    return _statuses(previous) != _statuses(report)
