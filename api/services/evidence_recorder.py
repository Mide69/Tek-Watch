"""Writes the compliance evidence log, on its own schedule.

Recording is deliberately not done when somebody opens the Security page. If it
were, the log would say more about who was looking than about the estate, and
two people refreshing would race each other for the same sequence number.

So a background pass evaluates compliance for each active customer and appends
only when there is something to record:

* every control that changed verdict since the last snapshot, so a fix is
  recorded as resolved at the time the agent's own data showed it fixed
* a snapshot, if any verdict changed, or if the last one is a day old

A quiet estate therefore produces one entry a day, and a busy one produces a
line per change. Both are small.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from config import load_config
from services import compliance, evidence, exposure, timestamping
from services.dynamodb import DynamoDBService
from services.timestream import TimestreamQueryService

logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 60 * 60
STARTUP_DELAY_SECONDS = 180
# A snapshot at least this often even when nothing changes, so the log shows a
# continuous record of assessment rather than gaps an assessor has to ask about.
SNAPSHOT_MAX_AGE = timedelta(hours=24)
# How often the chain is anchored to an independent timestamp. Daily is enough
# to prove when a week's worth of entries existed, and leaves the authority
# alone the rest of the time.
ANCHOR_MAX_AGE = timedelta(hours=24)


def _older_than(value: Any, age: timedelta, now: datetime) -> bool:
    """True when the stored time is missing, unreadable, or older than age."""
    if not value:
        return True
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return True
    if not when.tzinfo:
        when = when.replace(tzinfo=timezone.utc)
    return now - when >= age


def _due_for_snapshot(head: Dict[str, Any], now: datetime) -> bool:
    return _older_than((head.get("last_snapshot") or {}).get("recorded_at"), SNAPSHOT_MAX_AGE, now)


def _due_for_anchor(head: Dict[str, Any], now: datetime) -> bool:
    return _older_than(head.get("last_anchor_at"), ANCHOR_MAX_AGE, now)


def _stamp_for(prev_hash: str, now: datetime) -> Optional[Dict[str, Any]]:
    """The configured authority's token for this hash, or None.

    Separated so a test never reaches an outside service by accident, and so
    anchoring can be switched off with an empty TSA_URL.
    """
    url = load_config().tsa_url
    if not url:
        return None
    return timestamping.stamp(prev_hash, url=url, now=now)


def _anchor(
    customer_id: str,
    db_service: DynamoDBService,
    seq: int,
    prev_hash: str,
    now: datetime,
) -> Tuple[int, str, int]:
    """Ask an authority to timestamp the head of the chain, and record it.

    Best effort on purpose. If the authority is unreachable the log carries on
    unanchored and tries again tomorrow, because evidence must not depend on
    somebody else's uptime.
    """
    if prev_hash == evidence.GENESIS:
        return seq, prev_hash, 0          # nothing to anchor yet
    stamp = _stamp_for(prev_hash, now)
    if not stamp:
        return seq, prev_hash, 0

    seq += 1
    entry = evidence.build_entry(
        prev_hash=prev_hash,
        seq=seq,
        kind=evidence.ANCHOR,
        summary=f"Chain anchored with an independent timestamp from {stamp['authority']}",
        body=evidence.anchor_body(stamp),
        now=now,
    )
    if not db_service.append_evidence(customer_id, entry, last_anchor_at=entry["recorded_at"]):
        return seq - 1, prev_hash, 0
    return seq, entry["hash"], 1


def record_for_customer(
    customer_id: str,
    ts_service: TimestreamQueryService,
    db_service: DynamoDBService,
    now: Optional[datetime] = None,
) -> int:
    """One evaluation, and whatever it produces for the log. Returns entries written."""
    now = now or datetime.now(timezone.utc)
    report = compliance.evaluate(compliance.load_inventory(ts_service, customer_id), now=now)
    if not report.get("controls"):
        return 0

    head = db_service.evidence_head(customer_id)
    if not head.get("readable", True):
        # Could not read where the chain is. Appending now would fork it.
        return 0

    previous = (head.get("last_snapshot") or {}).get("body")
    seq = int(head.get("seq", 0))
    prev_hash = str(head.get("hash", evidence.GENESIS))
    written = 0

    for kind, summary, body in evidence.transitions(previous, report):
        seq += 1
        entry = evidence.build_entry(
            prev_hash=prev_hash, seq=seq, kind=kind, summary=summary, body=body, now=now
        )
        if not db_service.append_evidence(customer_id, entry):
            return written
        prev_hash, written = entry["hash"], written + 1

    if evidence.changed_since(previous, report) or _due_for_snapshot(head, now):
        body = evidence.snapshot_body(report, exposure.estimate(report))
        failed = sum(1 for c in report["controls"] if c["status"] == compliance.FAIL)
        passed = sum(1 for c in report["controls"] if c["status"] == compliance.PASS)
        seq += 1
        entry = evidence.build_entry(
            prev_hash=prev_hash,
            seq=seq,
            kind=evidence.SNAPSHOT,
            summary=f"Compliance assessment: {passed} passed, {failed} failed",
            body=body,
            now=now,
        )
        if db_service.append_evidence(
            customer_id,
            entry,
            last_snapshot={"recorded_at": entry["recorded_at"], "seq": seq, "body": body},
        ):
            prev_hash, written = entry["hash"], written + 1

    if _due_for_anchor(head, now):
        _, _, anchored = _anchor(customer_id, db_service, seq, prev_hash, now)
        written += anchored

    return written


async def evidence_recording_loop() -> None:
    """Background task: keep every active customer's evidence log current."""
    ts_service = TimestreamQueryService()
    db_service = DynamoDBService()
    logger.info("Evidence recording loop started (interval: %d min)", INTERVAL_SECONDS // 60)
    await asyncio.sleep(STARTUP_DELAY_SECONDS)

    while True:
        try:
            for customer in await asyncio.to_thread(db_service.list_customers):
                if customer.get("status") != "active":
                    continue
                try:
                    written = await asyncio.to_thread(
                        record_for_customer, customer["customer_id"], ts_service, db_service
                    )
                except Exception:
                    logger.exception("Evidence customer pass failed for %s", customer["customer_id"])
                    continue
                if written:
                    logger.info(
                        "Recorded %d evidence entr%s for %s",
                        written, "y" if written == 1 else "ies", customer["customer_id"],
                    )
        except Exception as exc:  # noqa: BLE001 — a bad pass must not end the loop
            logger.error("Evidence recording loop error: %s", exc)

        await asyncio.sleep(INTERVAL_SECONDS)
