"""Unit tests for the CloudFrontCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.cloudfront import CloudFrontCollector


def make_distribution(dist_id="E123ABC", domain="abc.cloudfront.net", status="Deployed", enabled=True):
    return {
        "Id": dist_id,
        "DomainName": domain,
        "Status": status,
        "Enabled": enabled,
        "PriceClass": "PriceClass_All",
        "Aliases": {"Items": []},
    }


@pytest.fixture
def collector():
    session = MagicMock()
    cf = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: cf if svc == "cloudfront" else cw
    c = CloudFrontCollector(session, "global", "TT-0001")
    c._cf = cf
    c._cw = cw
    return c, cf, cw


class TestCloudFrontCollector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "cloudfront"

    def test_no_distributions_returns_empty(self, collector):
        c, cf, _ = collector
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": []}}
        ]
        assert c.collect() == []

    def test_distribution_status_emitted(self, collector):
        c, cf, cw = collector
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": [make_distribution()]}}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        status_recs = [r for r in records if r.metric_name == "distribution_status"]
        assert len(status_recs) == 1
        assert status_recs[0].metric_value == "Deployed"
        assert status_recs[0].resource_id == "E123ABC"

    def test_undeployed_dist_skips_cw(self, collector):
        c, cf, cw = collector
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": [make_distribution(status="InProgress")]}}
        ]
        records = c.collect()
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_disabled_dist_skips_cw(self, collector):
        c, cf, cw = collector
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": [make_distribution(enabled=False)]}}
        ]
        records = c.collect()
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_cw_metric_emitted_for_deployed_dist(self, collector):
        c, cf, cw = collector
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": [make_distribution()]}}
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Sum": 1000.0}]
        }
        records = c.collect()
        assert len(records) > 1

    def test_access_denied_returns_empty(self, collector):
        c, cf, _ = collector
        cf.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListDistributions",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, cf, cw = collector
        cf.get_paginator.return_value.paginate.return_value = [
            {"DistributionList": {"Items": [make_distribution()]}}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
