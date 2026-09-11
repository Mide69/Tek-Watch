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
    assert {f["id"] for f in report["frameworks"]} == {"uk_gdpr", "cyber_essentials", "iso27001"}


@pytest.mark.asyncio
async def test_incidents_endpoint_wraps_list():
    rows = {"s3": [{"resource_id": "b", "resource_name": "b", "metrics": {},
                    "dimensions": {"public_access_blocked": "False"}}]}
    with patch("routers.security.TimestreamQueryService", return_value=inventory(rows)):
        result = await security.get_incidents(customer=CTX)
    assert [i["id"] for i in result["incidents"]] == ["s3-exposure:b"]
