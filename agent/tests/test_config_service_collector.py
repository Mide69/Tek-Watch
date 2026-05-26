"""Unit tests for the ConfigServiceCollector."""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.config_service import ConfigServiceCollector


def make_rule(name="s3-bucket-public-read-prohibited", compliance_type="NON_COMPLIANT"):
    return {
        "ConfigRuleName": name,
        "Compliance": {"ComplianceType": compliance_type},
    }


@pytest.fixture
def collector():
    session = MagicMock()
    config = MagicMock()
    session.client.return_value = config
    c = ConfigServiceCollector(session, "eu-west-1", "TT-0001")
    c._config = config
    return c, config


class TestConfigServiceCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "config"

    def test_no_rules_returns_summary_zeros(self, collector):
        c, config = collector
        config.get_paginator.return_value.paginate.return_value = [
            {"ComplianceByConfigRules": []}
        ]
        records = c.collect()
        compliant = next(r for r in records if r.metric_name == "compliant_rules_count")
        non_compliant = next(r for r in records if r.metric_name == "non_compliant_rules_count")
        assert compliant.metric_value == 0
        assert non_compliant.metric_value == 0

    def test_non_compliant_rule_recorded(self, collector):
        c, config = collector
        config.get_paginator.return_value.paginate.return_value = [
            {"ComplianceByConfigRules": [make_rule("bad-rule", "NON_COMPLIANT")]}
        ]
        records = c.collect()
        rule_recs = [r for r in records if r.metric_name == "compliance_status"]
        assert len(rule_recs) == 1
        assert rule_recs[0].resource_id == "bad-rule"
        assert rule_recs[0].metric_value == "NON_COMPLIANT"

    def test_compliant_rule_not_emitted_individually(self, collector):
        c, config = collector
        config.get_paginator.return_value.paginate.return_value = [
            {"ComplianceByConfigRules": [make_rule("good-rule", "COMPLIANT")]}
        ]
        records = c.collect()
        rule_recs = [r for r in records if r.metric_name == "compliance_status"]
        assert rule_recs == []

    def test_compliant_count_in_summary(self, collector):
        c, config = collector
        config.get_paginator.return_value.paginate.return_value = [
            {"ComplianceByConfigRules": [
                make_rule("rule-a", "COMPLIANT"),
                make_rule("rule-b", "COMPLIANT"),
                make_rule("rule-c", "NON_COMPLIANT"),
            ]}
        ]
        records = c.collect()
        compliant = next(r for r in records if r.metric_name == "compliant_rules_count")
        non_compliant = next(r for r in records if r.metric_name == "non_compliant_rules_count")
        assert compliant.metric_value == 2
        assert non_compliant.metric_value == 1

    def test_access_denied_returns_empty(self, collector):
        c, config = collector
        config.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "DescribeComplianceByConfigRule",
        )
        assert c.collect() == []

    def test_endpoint_error_returns_empty(self, collector):
        c, config = collector
        config.get_paginator.side_effect = EndpointResolutionError(msg="endpoint not available")
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, config = collector
        config.get_paginator.return_value.paginate.return_value = [
            {"ComplianceByConfigRules": []}
        ]
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
