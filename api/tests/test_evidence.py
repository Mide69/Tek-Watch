"""The evidence log: append-only, chained, and honest about what it proves."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services import evidence, evidence_recorder


def entry(seq, prev, kind=evidence.SNAPSHOT, body=None, now=None):
    return evidence.build_entry(
        prev_hash=prev, seq=seq, kind=kind, summary=f"entry {seq}",
        body=body or {"n": seq}, now=now or datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc),
    )


def chain(count):
    out, prev = [], evidence.GENESIS
    for i in range(1, count + 1):
        e = entry(i, prev)
        out.append(e)
        prev = e["hash"]
    return out


class TestChain:
    def test_a_written_chain_verifies(self):
        result = evidence.verify(chain(5))
        assert result["intact"] is True
        assert result["entries_checked"] == 5
        assert result["broken_at"] is None

    def test_an_empty_log_is_intact_not_broken(self):
        assert evidence.verify([])["intact"] is True

    def test_editing_a_body_breaks_the_chain_at_that_entry(self):
        entries = chain(5)
        entries[2]["body"] = {"n": "tampered"}
        result = evidence.verify(entries)
        assert result["intact"] is False
        assert result["broken_at"] == 3

    def test_editing_a_timestamp_breaks_the_chain(self):
        entries = chain(3)
        entries[1]["recorded_at"] = "2020-01-01T00:00:00+00:00"
        assert evidence.verify(entries)["intact"] is False

    def test_removing_an_entry_breaks_the_chain(self):
        entries = chain(4)
        del entries[1]
        assert evidence.verify(entries)["intact"] is False

    def test_order_is_taken_from_the_sequence_not_the_list(self):
        entries = chain(4)
        assert evidence.verify(list(reversed(entries)))["intact"] is True

    def test_hash_is_reproducible_from_the_stored_fields(self):
        e = entry(1, evidence.GENESIS)
        assert e["hash"] == evidence.entry_hash(
            evidence.GENESIS, 1, e["recorded_at"], e["kind"], e["body"]
        )

    def test_the_statement_does_not_claim_a_notarised_timestamp(self):
        # The plan called this "cryptographically timestamped". It is not: there
        # is no third party attesting to the time.
        assert "not a third-party notarised timestamp" in evidence.STATEMENT
        assert "tamper-evident" in evidence.STATEMENT


def report(*controls, evaluated_at="2026-09-17T12:00:00+00:00"):
    return {
        "evaluated_at": evaluated_at,
        "frameworks": [{"id": "uk_gdpr", "name": "UK GDPR", "score": 50, "passed": 1,
                        "failed": 1, "unknown": 0, "total": 2}],
        "controls": list(controls),
    }


def ctrl(cid, status, title="A control", severity="high", findings=()):
    return {"id": cid, "status": status, "title": title, "severity": severity,
            "detail": "detail", "findings": list(findings)}


class TestTransitions:
    def test_a_fix_is_recorded_as_resolved(self):
        before = report(ctrl("S3-01", "fail"))
        after = report(ctrl("S3-01", "pass"))
        kinds = evidence.transitions(before, after)
        assert len(kinds) == 1
        kind, summary, body = kinds[0]
        assert kind == evidence.RESOLVED
        assert body["from"] == "fail" and body["to"] == "pass"
        assert "S3-01" in summary

    def test_a_regression_is_recorded_too(self):
        kinds = evidence.transitions(report(ctrl("S3-01", "pass")), report(ctrl("S3-01", "fail")))
        assert kinds[0][0] == evidence.REGRESSED

    def test_unchanged_controls_produce_nothing(self):
        assert evidence.transitions(report(ctrl("S3-01", "fail")), report(ctrl("S3-01", "fail"))) == []

    def test_becoming_unknown_is_not_reported_as_a_fix(self):
        # The agent losing sight of a control is not the customer fixing it.
        kinds = evidence.transitions(report(ctrl("S3-01", "fail")), report(ctrl("S3-01", "unknown")))
        assert kinds == []

    def test_the_first_ever_evaluation_has_nothing_to_compare(self):
        assert evidence.transitions(None, report(ctrl("S3-01", "fail"))) == []


class TestSnapshotBody:
    def test_keeps_verdicts_and_drops_resource_names(self):
        body = evidence.snapshot_body(report(ctrl("S3-01", "fail", findings=[{"resource": "secret-bucket"}])))
        assert body["controls"][0]["status"] == "fail"
        assert body["controls"][0]["failing_resources"] == 1
        assert "secret-bucket" not in evidence.canonical(body)

    def test_carries_the_exposure_headline_when_given_one(self):
        body = evidence.snapshot_body(
            report(ctrl("S3-01", "fail")),
            {"failing_controls": 1, "direct_cost": {"display": "£2,000 to £3,000"},
             "comparable_enforcement": {"display": "£60,000"}},
        )
        assert body["exposure"]["direct_cost"] == "£2,000 to £3,000"


NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def recorder_services(head=None, controls=None):
    ts = MagicMock()
    db = MagicMock()
    db.evidence_head.return_value = head if head is not None else {
        "seq": 0, "hash": evidence.GENESIS, "readable": True,
    }
    db.append_evidence.return_value = True
    written = report(*(controls or [ctrl("S3-01", "fail"), ctrl("IAM-01", "pass")]))
    return ts, db, written


class TestRecorder:
    def _run(self, monkeypatch, head=None, controls=None, now=NOW):
        ts, db, written = recorder_services(head, controls)
        monkeypatch.setattr(evidence_recorder.compliance, "load_inventory", lambda *a, **k: {})
        monkeypatch.setattr(evidence_recorder.compliance, "evaluate", lambda inv, now=None: written)
        count = evidence_recorder.record_for_customer("TT-1", ts, db, now=now)
        return count, db

    def test_first_pass_records_a_snapshot(self, monkeypatch):
        count, db = self._run(monkeypatch)
        assert count == 1
        entry_written = db.append_evidence.call_args.args[1]
        assert entry_written["kind"] == evidence.SNAPSHOT
        assert entry_written["prev_hash"] == evidence.GENESIS
        assert entry_written["seq"] == 1

    def test_a_fix_writes_the_resolution_then_the_new_snapshot(self, monkeypatch):
        head = {
            "seq": 4,
            "hash": "a" * 64,
            "readable": True,
            "last_snapshot": {
                "recorded_at": NOW.isoformat(),
                "body": evidence.snapshot_body(report(ctrl("S3-01", "fail"))),
            },
        }
        count, db = self._run(monkeypatch, head=head, controls=[ctrl("S3-01", "pass")])
        assert count == 2
        kinds = [call.args[1]["kind"] for call in db.append_evidence.call_args_list]
        assert kinds == [evidence.RESOLVED, evidence.SNAPSHOT]
        seqs = [call.args[1]["seq"] for call in db.append_evidence.call_args_list]
        assert seqs == [5, 6]

    def test_each_entry_chains_onto_the_one_before(self, monkeypatch):
        head = {
            "seq": 1, "hash": "b" * 64, "readable": True,
            "last_snapshot": {"recorded_at": NOW.isoformat(),
                              "body": evidence.snapshot_body(report(ctrl("S3-01", "fail")))},
        }
        _, db = self._run(monkeypatch, head=head, controls=[ctrl("S3-01", "pass")])
        first, second = [c.args[1] for c in db.append_evidence.call_args_list]
        assert first["prev_hash"] == "b" * 64
        assert second["prev_hash"] == first["hash"]

    def test_nothing_is_written_when_nothing_changed_and_the_snapshot_is_fresh(self, monkeypatch):
        current = [ctrl("S3-01", "fail"), ctrl("IAM-01", "pass")]
        head = {
            "seq": 9, "hash": "c" * 64, "readable": True,
            "last_snapshot": {
                "recorded_at": (NOW - timedelta(hours=2)).isoformat(),
                "body": evidence.snapshot_body(report(*current)),
            },
        }
        count, db = self._run(monkeypatch, head=head, controls=current)
        assert count == 0
        db.append_evidence.assert_not_called()

    def test_a_day_without_change_still_records_a_snapshot(self, monkeypatch):
        current = [ctrl("S3-01", "fail"), ctrl("IAM-01", "pass")]
        head = {
            "seq": 9, "hash": "c" * 64, "readable": True,
            "last_snapshot": {
                "recorded_at": (NOW - timedelta(hours=25)).isoformat(),
                "body": evidence.snapshot_body(report(*current)),
            },
        }
        count, _ = self._run(monkeypatch, head=head, controls=current)
        assert count == 1

    def test_an_unreadable_head_writes_nothing_rather_than_forking_the_chain(self, monkeypatch):
        count, db = self._run(monkeypatch, head={"seq": 0, "hash": evidence.GENESIS, "readable": False})
        assert count == 0
        db.append_evidence.assert_not_called()

    def test_a_rejected_append_stops_the_pass(self, monkeypatch):
        ts, db, written = recorder_services(
            head={"seq": 2, "hash": "d" * 64, "readable": True,
                  "last_snapshot": {"recorded_at": NOW.isoformat(),
                                    "body": evidence.snapshot_body(report(ctrl("S3-01", "fail")))}},
            controls=[ctrl("S3-01", "pass")],
        )
        db.append_evidence.return_value = False
        monkeypatch.setattr(evidence_recorder.compliance, "load_inventory", lambda *a, **k: {})
        monkeypatch.setattr(evidence_recorder.compliance, "evaluate", lambda inv, now=None: written)
        assert evidence_recorder.record_for_customer("TT-1", ts, db, now=NOW) == 0
        assert db.append_evidence.call_count == 1

    def test_an_estate_with_no_controls_records_nothing(self, monkeypatch):
        ts, db, _ = recorder_services()
        monkeypatch.setattr(evidence_recorder.compliance, "load_inventory", lambda *a, **k: {})
        monkeypatch.setattr(evidence_recorder.compliance, "evaluate", lambda inv, now=None: {"controls": []})
        assert evidence_recorder.record_for_customer("TT-1", ts, db, now=NOW) == 0


@pytest.mark.parametrize("last,expected", [
    (None, True),
    ((NOW - timedelta(hours=1)).isoformat(), False),
    ((NOW - timedelta(hours=30)).isoformat(), True),
    ("not a date", True),
])
def test_snapshot_due(last, expected):
    head = {"last_snapshot": {"recorded_at": last}} if last else {}
    assert evidence_recorder._due_for_snapshot(head, NOW) is expected
