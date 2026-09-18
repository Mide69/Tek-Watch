"""Security router: field mapping from folded inventory, compliance, incidents."""
from unittest.mock import MagicMock, patch

import pytest

from routers import security

CTX = MagicMock(customer_id="TT-1")


def inventory(by_service):
    ts = MagicMock()
    ts.get_service_inventory.side_effect = lambda cid, svc, *a: by_service.get(svc, [])
    return ts


@pytest.mark.asyncio
async def test_guardduty_lists_findings_not_detector_rows():
    rows = {"guardduty": [
        {"resource_id": "det-1", "resource_name": "guardduty-eu-west-2", "region": "eu-west-2",
         "metrics": {"detector_enabled": 1, "findings_high_count": 1}, "dimensions": {}},
        {"resource_id": "f-1", "resource_name": "API called from a known malicious IP",
         "region": "eu-west-2", "metrics": {"finding_severity": 7.5},
         "dimensions": {"type": "UnauthorizedAccess:IAMUser/MaliciousIPCaller",
                        "resource_type": "AccessKey", "created_at": "2026-09-11T09:00:00Z"}},
    ]}
    with patch("routers.security.TimestreamQueryService", return_value=inventory(rows)):
        result = await security.get_guardduty_findings(customer=CTX, severity=None, region=None)
    assert result["findings"] == [{
        "finding_id": "f-1",
        "type": "UnauthorizedAccess:IAMUser/MaliciousIPCaller",
        "severity": "HIGH",
        "region": "eu-west-2",
        "resource": "AccessKey",
        "description": "API called from a known malicious IP",
        "updated_at": "2026-09-11T09:00:00Z",
        "count": 1,
    }]


@pytest.mark.parametrize("score,label", [(9.5, "CRITICAL"), (7.0, "HIGH"), (5, "MEDIUM"), (2, "LOW"), (None, "UNKNOWN")])
def test_guardduty_severity_bands(score, label):
    assert security._guardduty_severity(score) == label


@pytest.mark.asyncio
@pytest.mark.parametrize("raw,expected", [("false", False), ("true", True), (None, None)])
async def test_root_mfa_string_is_parsed(raw, expected):
    metrics = {"total_users": 4, "users_without_mfa_count": 1}
    if raw is not None:
        metrics["root_mfa_active"] = raw
    rows = {"iam": [{"resource_id": "iam", "metrics": metrics, "dimensions": {}}]}
    with patch("routers.security.TimestreamQueryService", return_value=inventory(rows)):
        result = await security.get_iam_summary(customer=CTX)
    assert result["summary"]["root_mfa_enabled"] is expected


@pytest.mark.asyncio
async def test_compliance_endpoint_evaluates_customer_data():
    rows = {"iam": [{"resource_id": "iam", "metrics": {"root_mfa_active": "false"}, "dimensions": {}}]}
    with patch("routers.security.TimestreamQueryService", return_value=inventory(rows)):
        report = await security.get_compliance(customer=CTX)
    root = next(c for c in report["controls"] if c["id"] == "IAM-02")
    assert root["status"] == "fail"
    assert {f["id"] for f in report["frameworks"]} == {
        "uk_gdpr", "cyber_essentials", "iso27001", "fca_ps21_3",
    }


@pytest.mark.asyncio
async def test_incidents_endpoint_wraps_list():
    rows = {"s3": [{"resource_id": "b", "resource_name": "b", "metrics": {},
                    "dimensions": {"public_access_blocked": "False"}}]}
    with patch("routers.security.TimestreamQueryService", return_value=inventory(rows)):
        result = await security.get_incidents(customer=CTX)
    assert [i["id"] for i in result["incidents"]] == ["s3-exposure:b"]


# ── Exposure and the evidence log ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compliance_carries_published_exposure_for_failing_controls():
    rows = {"s3": [{"resource_id": "b1", "resource_name": "b1", "region": "eu-west-2",
                    "metrics": {}, "dimensions": {"public_access_blocked": "false",
                                                  "encryption_enabled": "true",
                                                  "versioning_enabled": "true"}}]}
    with patch("routers.security.TimestreamQueryService", return_value=inventory(rows)):
        report = await security.get_compliance(customer=CTX)

    exposure = report["exposure"]
    assert exposure["failing_controls"] >= 1
    assert "not a prediction" in exposure["basis"]
    for item in exposure["items"]:
        assert item["references"], item["control_id"]
        assert all(
            r["source"].startswith(("https://ico.org.uk", "https://iasme.co.uk", "https://www.fca.org.uk"))
            for r in item["references"]
        )


@pytest.mark.asyncio
async def test_evidence_endpoint_returns_entries_and_the_honest_statement():
    db = MagicMock()
    db.list_evidence.return_value = [{"seq": 2, "kind": "snapshot", "hash": "h2"}]
    db.evidence_head.return_value = {"seq": 2, "hash": "h2"}
    with patch("routers.security.DynamoDBService", return_value=db):
        result = await security.get_evidence(limit=50, customer=CTX)
    assert result["entries"][0]["seq"] == 2
    assert result["total_recorded"] == 2
    assert "not a third-party notarised timestamp" in result["statement"]


@pytest.mark.asyncio
async def test_verify_endpoint_checks_the_stored_chain_not_a_stored_answer():
    from services import evidence as ev
    good = []
    prev = ev.GENESIS
    for i in (1, 2, 3):
        e = ev.build_entry(prev_hash=prev, seq=i, kind=ev.SNAPSHOT, summary="s", body={"i": i})
        good.append(e)
        prev = e["hash"]
    db = MagicMock()
    db.all_evidence.return_value = good
    with patch("routers.security.DynamoDBService", return_value=db):
        assert (await security.verify_evidence(customer=CTX))["intact"] is True

    good[1]["summary"] = "edited"          # the body is what the hash covers
    good[1]["body"] = {"i": "edited"}
    with patch("routers.security.DynamoDBService", return_value=db):
        broken = await security.verify_evidence(customer=CTX)
    assert broken["intact"] is False and broken["broken_at"] == 2


@pytest.mark.asyncio
async def test_export_is_a_csv_attachment_with_the_hashes():
    db = MagicMock()
    db.all_evidence.return_value = [
        {"seq": 1, "recorded_at": "2026-09-17T12:00:00+00:00", "kind": "snapshot",
         "summary": "Compliance assessment: 8 passed, 2 failed", "hash": "abc", "prev_hash": "0" * 64},
    ]
    with patch("routers.security.DynamoDBService", return_value=db):
        response = await security.export_evidence(customer=CTX)
    assert response.media_type == "text/csv"
    assert "attachment" in response.headers["content-disposition"]
    text = response.body.decode()
    assert "seq,recorded_at,kind,summary,hash,prev_hash" in text
    assert "abc" in text
