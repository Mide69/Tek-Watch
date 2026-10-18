"""Customer-visible integrity failures reproduced during the repository review."""
import base64
import io
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from services import compliance, evidence
from services.dynamodb import DynamoDBService, EvidenceReadError
from services.evidence_bundle import build_bundle

NOW = datetime(2026, 10, 18, 15, tzinfo=timezone.utc)


def control(inv, cid="S3-01"):
    return next(c for c in compliance.evaluate(inv, now=NOW)["controls"] if c["id"] == cid)


def bucket(when=NOW):
    return {"resource_id": "bucket", "last_seen": when.isoformat(),
            "dimensions": {"public_access_blocked": "True"}, "metrics": {}}


def chain():
    a = evidence.build_entry(prev_hash=evidence.GENESIS, seq=1, kind="snapshot", summary="display", body={"verdict": "unknown"})
    b = evidence.build_entry(prev_hash=a["hash"], seq=2, kind="snapshot", summary="display", body={"verdict": "pass"})
    return [a, b]


@pytest.mark.parametrize("runtime", [None, "not-a-runtime", "python3.9", "nodejs18.x", "python3.12"])
def test_quarantined_control_cannot_reassure_a_customer(runtime):
    r = {"resource_id": "fn", "last_seen": NOW.isoformat(), "dimensions": {"runtime": runtime} if runtime else {}}
    result = control({"lambda": [r]}, "LAM-01")
    assert result["status"] == "unknown" and not result["eligible"]


def test_retired_runtime_and_unrecognised_runtime_are_distinct_in_catalogue():
    retired = compliance._lambda_supported_runtimes({"lambda": [{"dimensions": {"runtime": "python3.9"}}]})
    unknown = compliance._lambda_supported_runtimes({"lambda": [{"dimensions": {"runtime": "brand-new"}}]})
    missing = compliance._lambda_supported_runtimes({"lambda": [{"resource_id": "fn"}]})
    assert retired.status == "fail"
    assert unknown.status == missing.status == "unknown"


@pytest.mark.parametrize("when", [NOW - timedelta(hours=25), NOW + timedelta(hours=1)])
def test_stale_or_future_observation_is_not_a_pass(when):
    assert control({"s3": [bucket(when)]})["status"] == "unknown"


def test_fresh_metric_cannot_refresh_an_old_security_setting():
    r = bucket()
    r["field_observed_at"] = {"cpu": NOW.isoformat(), "public_access_blocked": (NOW - timedelta(days=2)).isoformat()}
    assert control({"s3": [r]})["status"] == "unknown"


def test_assessment_retains_observation_rule_and_pack_identity():
    r = compliance.evaluate({"s3": [bucket()]}, now=NOW)
    c = next(c for c in r["controls"] if c["id"] == "S3-01")
    assert c["observed_at"] == NOW.isoformat() and c["rule_version"]
    assert c["observations"][0]["resource_id"] == "bucket"
    assert r["eligible_controls"] == 23
    assert len(r["pack"]["sha256"]) == len(r["pack"]["engine_sha256"]) == 64
    assert evidence.snapshot_body(r)["controls"] == [
        {"id": x["id"], "title": x["title"], "status": x["status"], "severity": x["severity"],
         "failing_resources": len(x["findings"]), "observed_at": x["observed_at"],
         "rule_version": x["rule_version"], "observations": x["observations"], "references": x["references"]}
        for x in r["controls"]]


def test_re_evaluation_of_old_data_does_not_resolve_a_finding():
    previous = {"evaluated_at": NOW.isoformat(), "controls": [{"id": "S3-01", "status": "fail"}]}
    new = {"evaluated_at": (NOW + timedelta(hours=1)).isoformat(), "controls": [
        {"id": "S3-01", "status": "pass", "observed_at": NOW.isoformat()}]}
    assert evidence.transitions(previous, new) == []
    new["controls"][0]["observed_at"] = (NOW + timedelta(minutes=1)).isoformat()
    assert evidence.transitions(previous, new)[0][2]["observed_at"] != new["evaluated_at"]


def test_gapped_duplicate_and_truncated_logs_fail_verification():
    entries = chain()
    head = {"seq": 2, "hash": entries[-1]["hash"]}
    assert not evidence.verify(entries[:1], expected_head=head)["intact"]
    assert not evidence.verify([entries[0], entries[0]])["intact"]
    wrong = evidence.build_entry(prev_hash=evidence.GENESIS, seq=5, kind="snapshot", summary="s", body={})
    assert not evidence.verify([wrong])["intact"]


def test_bundle_can_be_verified_offline_and_detects_tampering(tmp_path):
    entries = chain()
    payload = build_bundle(entries, {"seq": 2, "hash": entries[-1]["hash"]})
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        z.extractall(tmp_path)
    result = subprocess.run([sys.executable, str(tmp_path / "verify.py"), "--expected-head", entries[-1]["hash"]], capture_output=True)
    assert result.returncode == 0, result.stderr
    (tmp_path / "entries.json").write_text("[]")
    assert subprocess.run([sys.executable, str(tmp_path / "verify.py")], capture_output=True).returncode != 0


def test_bundle_includes_exact_timestamp_response_bytes():
    entries = chain()
    token = b"synthetic-response-not-a-verified-signature"
    import hashlib
    entry = evidence.build_entry(prev_hash=entries[-1]["hash"], seq=3, kind=evidence.ANCHOR, summary="response received",
                                 body={"token_b64": base64.b64encode(token).decode(), "token_sha256": hashlib.sha256(token).hexdigest(),
                                       "anchored_hash": entries[-1]["hash"]})
    entries.append(entry)
    with zipfile.ZipFile(io.BytesIO(build_bundle(entries, {"seq": 3, "hash": entry["hash"]}))) as z:
        assert z.read("anchors/3.tsr") == token


def service():
    db = DynamoDBService.__new__(DynamoDBService)
    db._customers = MagicMock(name="table")
    db._customers.name = "customers"
    db._transaction_client = MagicMock()
    return db


def test_append_is_one_conditional_atomic_transaction_and_retries_identically():
    db = service()
    item = chain()[0]
    assert db.append_evidence("TT-1", item)
    first = db._transaction_client.transact_write_items.call_args
    assert db.append_evidence("TT-1", item)
    assert first == db._transaction_client.transact_write_items.call_args
    tx = first.kwargs["TransactItems"]
    assert len(tx) == 2 and "ConditionExpression" in tx[0]["Put"] and "ConditionExpression" in tx[1]["Update"]
    db._customers.put_item.assert_not_called()
    db._customers.update_item.assert_not_called()


def test_rejected_transaction_is_not_reported_written():
    db = service()
    db._transaction_client.transact_write_items.side_effect = ClientError({"Error": {"Code": "TransactionCanceledException"}}, "TransactWriteItems")
    assert not db.append_evidence("TT-1", chain()[0])


def test_evidence_read_failure_and_explicit_limit_never_return_a_valid_prefix():
    db = service()
    db._customers.query.side_effect = [{"Items": chain()[:1], "LastEvaluatedKey": {"k": "next"}}, ClientError({"Error": {"Code": "InternalServerError"}}, "Query")]
    with pytest.raises(EvidenceReadError):
        db.all_evidence("TT-1")
    db._customers.query.side_effect = None
    db._customers.query.return_value = {"Items": chain()}
    with pytest.raises(EvidenceReadError):
        db.all_evidence("TT-1", cap=1)


def test_customer_scan_reads_all_pages_even_when_first_page_has_no_profiles():
    db = service()
    db._customers.scan.side_effect = [{"Items": [], "LastEvaluatedKey": {"k": "next"}}, {"Items": [{"customer_id": "TT-2"}]}]
    assert db.list_customers() == [{"customer_id": "TT-2"}]
    assert db._customers.scan.call_args.kwargs["ExclusiveStartKey"] == {"k": "next"}


def test_pending_recheck_reuses_its_original_boundary():
    db = service()
    db._customers.put_item.side_effect = ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
    db._customers.get_item.return_value = {"Item": {"requested_at": "2026-10-18T12:00:00+00:00"}}
    assert db.recheck_request("TT-1", "S3-01", NOW.isoformat()) == "2026-10-18T12:00:00+00:00"


def test_recovery_previews_a_legacy_orphan_and_refuses_conflicting_history():
    db = service()
    entries = chain()
    db.evidence_head = MagicMock(return_value={"seq": 1, "hash": entries[0]["hash"], "readable": True})
    db.all_evidence = MagicMock(return_value=entries)
    assert db.recover_evidence_head("TT-1")["seq"] == 2
    db._customers.update_item.assert_not_called()
    db.recover_evidence_head("TT-1", apply=True)
    assert "ConditionExpression" in db._customers.update_item.call_args.kwargs
    db.evidence_head.return_value["hash"] = "wrong"
    with pytest.raises(EvidenceReadError):
        db.recover_evidence_head("TT-1", apply=True)


def test_oversized_entry_is_not_reported_as_recorded():
    db = service()
    item = evidence.build_entry(prev_hash=evidence.GENESIS, seq=1, kind="snapshot", summary="large", body={"payload": "x" * 350_000})
    assert not db.append_evidence("TT-1", item)
    db._transaction_client.transact_write_items.assert_not_called()


def test_permission_policy_explicitly_denies_payload_reads_and_is_shared_with_terraform():
    policy = json.loads((Path(compliance.__file__).with_name("agent_policy.json")).read_text())
    allows = {a for s in policy["Statement"] if s["Effect"] == "Allow" for a in s["Action"]}
    denies = {a for s in policy["Statement"] if s["Effect"] == "Deny" for a in s["Action"]}
    assert {"s3:GetObject*", "secretsmanager:GetSecretValue", "dynamodb:Scan", "kms:Decrypt"} <= denies
    assert {"lambda:ListFunctions", "cloudwatch:GetMetricStatistics", "s3:GetEncryptionConfiguration"} <= allows
    assert not allows.intersection(denies)
    tf = (Path(__file__).resolve().parents[2] / "infrastructure/terraform/modules/ecs/main.tf").read_text()
    assert "api/services/agent_policy.json" in tf and "aws:policy/ReadOnlyAccess" not in tf


def test_multi_service_inventory_reads_numeric_history_once_and_retains_field_age():
    from services.timestream import TimestreamQueryService
    ts = TimestreamQueryService.__new__(TimestreamQueryService)
    ts._events_table = MagicMock()
    old = (NOW - timedelta(days=2)).isoformat()
    ts._iter_metrics_by_customer = MagicMock(return_value=iter([
        {"resource_id": "r", "service": "s3", "metric_name": "cpu", "value": 1, "time": NOW.isoformat()},
    ]))
    ts._paginated_query = MagicMock(side_effect=[[
        {"resource_id": "r", "service": "s3", "metric_name": "state", "value": "active", "time": old,
         "dimensions": {"public_access_blocked": "True"}},
    ], []])
    result = ts.get_services_inventory("TT-1", ("s3", "iam"))
    ts._iter_metrics_by_customer.assert_called_once()
    assert result["s3"][0]["field_observed_at"]["public_access_blocked"] == old


def test_configuration_alert_does_not_invent_breach_awareness_time():
    from services import calendar
    incident = {"id": "i", "type": "s3_public_exposure", "detected_at": NOW.isoformat(), "affected": []}
    entry = calendar._breach_clocks([incident], NOW)[0]
    assert entry.due_at is None and entry.kind == calendar.TRIAGE


@pytest.mark.parametrize("runner_output,code", [("ERROR during collection", 2), ("no tests ran", 0)])
def test_summary_fails_closed_on_runner_errors_or_empty_suites(tmp_path, runner_output, code):
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "python").write_text(f"#!/bin/sh\necho '{runner_output}'\nexit {code}\n")
    (tmp_path / "npx").write_text("#!/bin/sh\necho 'Tests: 1 passed, 1 total'\nexit 0\n")
    for p in tmp_path.iterdir():
        p.chmod(0o755)
    import os
    result = subprocess.run(["bash", str(root / "scripts/test-summary.sh")], env={**os.environ, "PATH": str(tmp_path) + ":" + os.environ["PATH"]}, capture_output=True)
    assert result.returncode != 0


def test_compliance_numeric_inventory_read_failure_propagates():
    from services.timestream import TimestreamQueryService
    ts = TimestreamQueryService.__new__(TimestreamQueryService)
    ts._metrics_table = MagicMock()
    ts._events_table = MagicMock()
    ts._iter_query = MagicMock(side_effect=ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "retry"}}, "Query"))
    with pytest.raises(ClientError):
        ts.get_services_inventory("TT-1", ("s3",))
