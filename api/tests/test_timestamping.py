"""RFC 3161 anchoring: the bytes on the wire, and never blocking the log.

Hand-written ASN.1 needs tests that check the actual encoding, not just that
the function returned something. A malformed request is refused by the
authority, and a request that encodes the wrong digest would anchor the wrong
thing while looking perfectly healthy.
"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest

from services import evidence, evidence_recorder, timestamping

DIGEST = hashlib.sha256(b"chain head").digest()
NOW = datetime(2026, 9, 18, 9, 0, tzinfo=timezone.utc)


def parse(data, offset=0):
    return timestamping._read_tlv(data, offset)


class TestRequestEncoding:
    def test_the_request_is_a_sequence_holding_the_digest(self):
        request = timestamping.build_request(DIGEST, nonce=1234)
        tag, body, end = parse(request)
        assert tag == 0x30                    # SEQUENCE
        assert end == len(request)            # nothing trailing

        tag, version, offset = parse(body)
        assert (tag, version) == (0x02, b"\x01")           # version 1

        tag, imprint, offset = parse(body, offset)
        assert tag == 0x30
        assert DIGEST in imprint

    def test_the_hash_algorithm_is_named_as_sha256(self):
        request = timestamping.build_request(DIGEST, nonce=1)
        _, body, _ = parse(request)
        _, imprint, _ = parse(body, parse(body)[2])
        _, algorithm, _ = parse(imprint)
        assert timestamping._SHA256_OID in algorithm

    def test_the_nonce_travels_so_a_replayed_answer_can_be_spotted(self):
        one = timestamping.build_request(DIGEST, nonce=0x1122334455667788)
        two = timestamping.build_request(DIGEST, nonce=0x99AABBCCDDEEFF00)
        assert one != two
        assert bytes.fromhex("1122334455667788") in one

    def test_certificates_are_requested_so_a_token_can_be_verified_alone(self):
        assert b"\x01\x01\xff" in timestamping.build_request(DIGEST, nonce=1, cert_req=True)
        assert b"\x01\x01\x00" in timestamping.build_request(DIGEST, nonce=1, cert_req=False)

    def test_long_values_use_multi_byte_lengths(self):
        assert timestamping._length(127) == b"\x7f"
        assert timestamping._length(128) == b"\x81\x80"
        assert timestamping._length(300) == b"\x82\x01\x2c"

    def test_a_digest_of_the_wrong_size_is_refused(self):
        with pytest.raises(ValueError):
            timestamping.build_request(b"too short", nonce=1)


def response(status: int, token: bytes = b"\x04\x02ok") -> bytes:
    status_info = timestamping._tlv(0x30, timestamping._integer(status))
    return timestamping._tlv(0x30, status_info + token)


class TestResponseParsing:
    @pytest.mark.parametrize("status", [0, 1, 2, 5])
    def test_the_status_is_read_back(self, status):
        assert timestamping.parse_status(response(status)) == status

    def test_rubbish_is_rejected_rather_than_read_as_success(self):
        for bad in (b"", b"\x30", b"not der at all", b"\x30\x84\xff\xff\xff\xff"):
            with pytest.raises(ValueError):
                timestamping.parse_status(bad)


def transport(handler):
    return MagicMock(side_effect=handler)


class TestStamp:
    def _post(self, monkeypatch, result):
        calls = {}

        def fake_post(url, content=None, headers=None, timeout=None):
            calls["url"], calls["content"], calls["headers"] = url, content, headers
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(timestamping.httpx, "post", fake_post)
        return calls

    def _ok(self, status=0):
        reply = MagicMock()
        reply.content = response(status)
        reply.raise_for_status = MagicMock()
        return reply

    def test_a_granted_token_is_returned_with_everything_needed_to_check_it(self, monkeypatch):
        calls = self._post(monkeypatch, self._ok())
        head = "a" * 64
        stamp = timestamping.stamp(head, url="https://tsa.example/tsr", now=NOW)

        assert stamp["anchored_hash"] == head
        assert stamp["authority"] == "https://tsa.example/tsr"
        assert stamp["requested_at"] == NOW.isoformat()
        assert base64.b64decode(stamp["token_b64"]) == response(0)
        assert stamp["token_sha256"] == hashlib.sha256(response(0)).hexdigest()
        assert "openssl ts -verify" in stamp["verify"]
        assert calls["headers"]["Content-Type"] == "application/timestamp-query"

    def test_the_request_carries_the_hash_being_anchored(self, monkeypatch):
        calls = self._post(monkeypatch, self._ok())
        head = hashlib.sha256(b"real head").hexdigest()
        timestamping.stamp(head, url="https://tsa.example/tsr")
        assert bytes.fromhex(head) in calls["content"]

    def test_a_refusal_is_not_stored_as_proof(self, monkeypatch):
        self._post(monkeypatch, self._ok(status=2))       # rejection
        assert timestamping.stamp("a" * 64, url="https://tsa.example/tsr") is None

    @pytest.mark.parametrize("failure", [
        httpx.ConnectTimeout("too slow"),
        httpx.HTTPError("refused"),
        RuntimeError("something else entirely"),
    ])
    def test_an_authority_that_is_down_never_raises(self, monkeypatch, failure):
        # Evidence must not depend on somebody else's uptime.
        self._post(monkeypatch, failure)
        assert timestamping.stamp("a" * 64, url="https://tsa.example/tsr") is None

    def test_a_value_that_is_not_a_hash_is_not_sent_anywhere(self, monkeypatch):
        calls = self._post(monkeypatch, self._ok())
        assert timestamping.stamp("not a hash", url="https://tsa.example/tsr") is None
        assert calls == {}

    def test_no_authority_configured_means_no_call(self, monkeypatch):
        calls = self._post(monkeypatch, self._ok())
        assert timestamping.stamp("a" * 64, url="") is None
        assert calls == {}


def head(seq=3, hash_value="b" * 64, anchored_at=None, prior_status="pass"):
    """A stored head. The prior status differs from the report by default, so a
    pass writes a snapshot and the anchor has something of today to chain onto."""
    return {
        "seq": seq, "hash": hash_value, "readable": True,
        "last_snapshot": {
            "recorded_at": NOW.isoformat(),
            "body": {"controls": [{"id": "S3-01", "status": prior_status}]},
        },
        "last_anchor_at": anchored_at,
    }


def a_stamp(hash_value):
    return {
        "anchored_hash": hash_value, "authority": "https://tsa.example/tsr",
        "status": 0, "nonce": "12345", "requested_at": NOW.isoformat(),
        "token_b64": "dG9rZW4=", "token_sha256": "c" * 64,
        "verify": timestamping.VERIFY_INSTRUCTIONS,
    }


class TestAnchoringInTheRecorder:
    def _run(self, monkeypatch, stored_head, stamp=None, controls=None):
        ts, db = MagicMock(), MagicMock()
        db.evidence_head.return_value = stored_head
        db.append_evidence.return_value = True
        report = {
            "evaluated_at": NOW.isoformat(),
            "frameworks": [],
            "controls": controls or [{"id": "S3-01", "status": "fail", "title": "t",
                                      "severity": "high", "detail": "d", "findings": []}],
        }
        monkeypatch.setattr(evidence_recorder.compliance, "load_inventory", lambda *a, **k: {})
        monkeypatch.setattr(evidence_recorder.compliance, "evaluate", lambda inv, now=None: report)
        # The stub answers about whatever hash it is handed, the way a real
        # authority does, so a test cannot pass while the wrong thing is anchored.
        monkeypatch.setattr(
            evidence_recorder, "_stamp_for",
            lambda h, n: {**stamp, "anchored_hash": h} if stamp else None,
        )
        written = evidence_recorder.record_for_customer("TT-1", ts, db, now=NOW)
        return written, db

    def test_a_log_that_has_never_been_anchored_gets_anchored(self, monkeypatch):
        written, db = self._run(monkeypatch, head(), stamp=a_stamp("b" * 64))
        kinds = [c.args[1]["kind"] for c in db.append_evidence.call_args_list]
        assert evidence.ANCHOR in kinds
        anchor = next(c.args[1] for c in db.append_evidence.call_args_list
                      if c.args[1]["kind"] == evidence.ANCHOR)
        assert anchor["body"]["token_b64"] == "dG9rZW4="
        assert "openssl" in anchor["body"]["verify"]

    def test_the_anchor_covers_the_entry_before_it(self, monkeypatch):
        _, db = self._run(monkeypatch, head(), stamp=a_stamp("b" * 64))
        appended = [c.args[1] for c in db.append_evidence.call_args_list]
        anchor = next(e for e in appended if e["kind"] == evidence.ANCHOR)
        before = appended[appended.index(anchor) - 1]
        assert anchor["prev_hash"] == before["hash"]
        assert anchor["body"]["anchored_hash"] == before["hash"]

    def test_a_quiet_day_anchors_the_head_it_already_had(self, monkeypatch):
        # Nothing changed, so nothing new is written and the anchor covers the
        # last entry, which is exactly what should be proved to exist.
        _, db = self._run(monkeypatch, head(prior_status="fail"), stamp=a_stamp("b" * 64))
        [only] = [c.args[1] for c in db.append_evidence.call_args_list]
        assert only["kind"] == evidence.ANCHOR
        assert only["prev_hash"] == "b" * 64

    def test_the_anchor_time_is_stored_so_tomorrow_knows(self, monkeypatch):
        _, db = self._run(monkeypatch, head(), stamp=a_stamp("b" * 64))
        anchor_call = next(c for c in db.append_evidence.call_args_list
                           if c.args[1]["kind"] == evidence.ANCHOR)
        assert anchor_call.kwargs["last_anchor_at"] == anchor_call.args[1]["recorded_at"]

    def test_a_log_anchored_this_morning_is_not_anchored_again(self, monkeypatch):
        recent = head(anchored_at=(NOW - timedelta(hours=3)).isoformat())
        _, db = self._run(monkeypatch, recent, stamp=a_stamp("b" * 64))
        kinds = [c.args[1]["kind"] for c in db.append_evidence.call_args_list]
        assert evidence.ANCHOR not in kinds

    def test_an_anchor_a_day_old_is_renewed(self, monkeypatch):
        old = head(anchored_at=(NOW - timedelta(hours=25)).isoformat())
        _, db = self._run(monkeypatch, old, stamp=a_stamp("b" * 64))
        kinds = [c.args[1]["kind"] for c in db.append_evidence.call_args_list]
        assert evidence.ANCHOR in kinds

    def test_an_authority_that_is_down_leaves_the_rest_of_the_log_intact(self, monkeypatch):
        written, db = self._run(monkeypatch, head(), stamp=None)
        kinds = [c.args[1]["kind"] for c in db.append_evidence.call_args_list]
        assert evidence.ANCHOR not in kinds
        assert written >= 1            # the snapshot was still recorded

    def test_an_empty_chain_has_nothing_to_anchor(self, monkeypatch):
        empty = {"seq": 0, "hash": evidence.GENESIS, "readable": True}
        stamped = []
        monkeypatch.setattr(evidence_recorder, "_stamp_for",
                            lambda h, n: stamped.append(h) or a_stamp(h))
        ts, db = MagicMock(), MagicMock()
        db.evidence_head.return_value = empty
        db.append_evidence.return_value = True
        monkeypatch.setattr(evidence_recorder.compliance, "load_inventory", lambda *a, **k: {})
        monkeypatch.setattr(evidence_recorder.compliance, "evaluate", lambda inv, now=None: {
            "evaluated_at": NOW.isoformat(), "frameworks": [],
            "controls": [{"id": "S3-01", "status": "fail", "title": "t", "severity": "high",
                          "detail": "d", "findings": []}],
        })
        evidence_recorder.record_for_customer("TT-1", ts, db, now=NOW)
        # The snapshot is written first, so the hash anchored is that snapshot's,
        # never the genesis value.
        assert stamped and stamped[0] != evidence.GENESIS
