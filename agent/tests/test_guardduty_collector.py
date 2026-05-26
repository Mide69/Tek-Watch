"""Unit tests for the GuardDutyCollector."""
import pytest
from unittest.mock import MagicMock, call
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.guardduty import GuardDutyCollector


def make_finding(severity=7.5, title="Recon:IAMUser/MaliciousIPCaller", type_="Recon"):
    return {
        "Id": "abc123",
        "Title": title,
        "Severity": severity,
        "Type": type_,
        "CreatedAt": "2026-01-01T00:00:00Z",
        "Resource": {"ResourceType": "AccessKey"},
    }


@pytest.fixture
def collector():
    session = MagicMock()
    gd = MagicMock()
    session.client.return_value = gd
    c = GuardDutyCollector(session, "eu-west-1", "TT-0001")
    c._gd = gd
    return c, gd


class TestGuardDutyCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "guardduty"

    def test_no_detectors_returns_empty(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": []}
        assert c.collect() == []

    def test_zero_findings_emits_zero_counts(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": ["det-abc"]}
        gd.get_paginator.return_value.paginate.return_value = [{"FindingIds": []}]

        records = c.collect()
        names = {r.metric_name for r in records}
        assert "findings_low_count" in names
        assert "findings_high_count" in names
        assert "findings_critical_count" in names
        assert all(r.metric_value == 0 for r in records)

    def test_high_severity_finding_counted_correctly(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": ["det-abc"]}
        gd.get_paginator.return_value.paginate.return_value = [{"FindingIds": ["f1"]}]
        gd.get_findings.return_value = {"Findings": [make_finding(severity=7.5)]}

        records = c.collect()
        high = next(r for r in records if r.metric_name == "findings_high_count")
        assert high.metric_value == 1
        critical = next(r for r in records if r.metric_name == "findings_critical_count")
        assert critical.metric_value == 0

    def test_critical_severity_finding_counted(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": ["det-abc"]}
        gd.get_paginator.return_value.paginate.return_value = [{"FindingIds": ["f1"]}]
        gd.get_findings.return_value = {"Findings": [make_finding(severity=9.0)]}

        records = c.collect()
        critical = next(r for r in records if r.metric_name == "findings_critical_count")
        assert critical.metric_value == 1

    def test_individual_finding_record_emitted(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": ["det-abc"]}
        gd.get_paginator.return_value.paginate.return_value = [{"FindingIds": ["f1"]}]
        gd.get_findings.return_value = {"Findings": [make_finding(severity=7.5)]}

        records = c.collect()
        finding_recs = [r for r in records if r.metric_name == "finding_severity"]
        assert len(finding_recs) == 1
        assert finding_recs[0].metric_value == 7.5

    def test_top_10_finding_limit(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": ["det-abc"]}
        finding_ids = [f"f{i}" for i in range(15)]
        gd.get_paginator.return_value.paginate.return_value = [{"FindingIds": finding_ids}]
        gd.get_findings.return_value = {
            "Findings": [make_finding(severity=float(i)) for i in range(15)]
        }

        records = c.collect()
        finding_recs = [r for r in records if r.metric_name == "finding_severity"]
        assert len(finding_recs) <= 10

    def test_access_denied_returns_empty(self, collector):
        c, gd = collector
        gd.list_detectors.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListDetectors",
        )
        assert c.collect() == []

    def test_endpoint_resolution_error_returns_empty(self, collector):
        c, gd = collector
        gd.list_detectors.side_effect = EndpointResolutionError(msg="endpoint not available")
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, gd = collector
        gd.list_detectors.return_value = {"DetectorIds": ["det-abc"]}
        gd.get_paginator.return_value.paginate.return_value = [{"FindingIds": []}]

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
