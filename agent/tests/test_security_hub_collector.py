"""Unit tests for the SecurityHubCollector."""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.security_hub import SecurityHubCollector


def make_finding(severity="HIGH"):
    return {"Severity": {"Label": severity}}


@pytest.fixture
def collector():
    session = MagicMock()
    sh = MagicMock()
    session.client.return_value = sh
    c = SecurityHubCollector(session, "eu-west-1", "TT-0001")
    c._sh = sh
    return c, sh


class TestSecurityHubCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "security_hub"

    def test_no_findings_returns_summary_zeros(self, collector):
        c, sh = collector
        sh.get_paginator.return_value.paginate.return_value = [{"Findings": []}]

        records = c.collect()
        total = next(r for r in records if r.metric_name == "findings_total_count")
        assert total.metric_value == 0

    def test_all_severity_buckets_emitted(self, collector):
        c, sh = collector
        sh.get_paginator.return_value.paginate.return_value = [{"Findings": []}]

        records = c.collect()
        metric_names = {r.metric_name for r in records}
        for sev in ("critical", "high", "medium", "low", "informational"):
            assert f"findings_{sev}_count" in metric_names

    def test_finding_counts_by_severity(self, collector):
        c, sh = collector
        sh.get_paginator.return_value.paginate.return_value = [
            {"Findings": [
                make_finding("CRITICAL"),
                make_finding("CRITICAL"),
                make_finding("HIGH"),
                make_finding("MEDIUM"),
            ]}
        ]
        records = c.collect()
        critical = next(r for r in records if r.metric_name == "findings_critical_count")
        high = next(r for r in records if r.metric_name == "findings_high_count")
        medium = next(r for r in records if r.metric_name == "findings_medium_count")
        assert critical.metric_value == 2
        assert high.metric_value == 1
        assert medium.metric_value == 1

    def test_total_count_is_sum_of_severities(self, collector):
        c, sh = collector
        sh.get_paginator.return_value.paginate.return_value = [
            {"Findings": [
                make_finding("HIGH"),
                make_finding("LOW"),
                make_finding("INFORMATIONAL"),
            ]}
        ]
        records = c.collect()
        total = next(r for r in records if r.metric_name == "findings_total_count")
        assert total.metric_value == 3

    def test_access_denied_returns_empty(self, collector):
        c, sh = collector
        sh.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "GetFindings",
        )
        assert c.collect() == []

    def test_invalid_access_returns_empty(self, collector):
        c, sh = collector
        sh.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "InvalidAccessException", "Message": "not enabled"}},
            "GetFindings",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, sh = collector
        sh.get_paginator.return_value.paginate.return_value = [{"Findings": []}]

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
