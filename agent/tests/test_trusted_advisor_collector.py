"""Unit tests for the TrustedAdvisorCollector."""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.trusted_advisor import TrustedAdvisorCollector


def make_check(check_id="Qch7DwouX1", name="MFA on Root Account", category="security"):
    return {"id": check_id, "name": name, "category": category}


def make_check_result(status="ok"):
    return {"result": {"status": status}}


@pytest.fixture
def collector():
    session = MagicMock()
    support = MagicMock()
    session.client.return_value = support
    c = TrustedAdvisorCollector(session, "global", "TT-0001")
    c._support = support
    return c, support


class TestTrustedAdvisorCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "trusted_advisor"

    def test_no_checks_returns_empty(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.return_value = {"checks": []}
        assert c.collect() == []

    def test_check_status_recorded(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.return_value = {
            "checks": [make_check()]
        }
        support.describe_trusted_advisor_check_result.return_value = make_check_result("ok")

        records = c.collect()
        check_recs = [r for r in records if r.metric_name == "check_status"]
        assert len(check_recs) == 1
        assert check_recs[0].metric_value == "ok"
        assert check_recs[0].resource_name == "MFA on Root Account"

    def test_warning_check_counted_in_summary(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.return_value = {
            "checks": [make_check(category="security")]
        }
        support.describe_trusted_advisor_check_result.return_value = make_check_result("warning")

        records = c.collect()
        summary_recs = [r for r in records if r.metric_name == "warning_checks_count"]
        security_summary = next(
            (r for r in summary_recs if r.dimensions.get("category") == "security"), None
        )
        assert security_summary is not None
        assert security_summary.metric_value == 1

    def test_error_check_counted_in_summary(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.return_value = {
            "checks": [make_check(category="cost_optimizing")]
        }
        support.describe_trusted_advisor_check_result.return_value = make_check_result("error")

        records = c.collect()
        error_recs = [r for r in records if r.metric_name == "error_checks_count"]
        cost_summary = next(
            (r for r in error_recs if r.dimensions.get("category") == "cost_optimizing"), None
        )
        assert cost_summary is not None
        assert cost_summary.metric_value == 1

    def test_category_summary_always_emitted(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.return_value = {
            "checks": [make_check()]
        }
        support.describe_trusted_advisor_check_result.return_value = make_check_result("ok")

        records = c.collect()
        summary_recs = [r for r in records if r.metric_name in (
            "ok_checks_count", "warning_checks_count", "error_checks_count"
        )]
        # 5 categories × 3 statuses = 15 summary records
        assert len(summary_recs) == 15

    def test_subscription_required_returns_empty(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.side_effect = ClientError(
            {"Error": {"Code": "SubscriptionRequiredException", "Message": "need Business plan"}},
            "DescribeTrustedAdvisorChecks",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, support = collector
        support.describe_trusted_advisor_checks.return_value = {
            "checks": [make_check()]
        }
        support.describe_trusted_advisor_check_result.return_value = make_check_result("ok")

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
