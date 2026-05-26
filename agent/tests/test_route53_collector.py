"""Unit tests for the Route53Collector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.route53 import Route53Collector


def make_hosted_zone(zone_id="/hostedzone/Z123ABC", name="example.com.", record_count=15, private=False):
    return {
        "Id": zone_id,
        "Name": name,
        "ResourceRecordSetCount": record_count,
        "Config": {"PrivateZone": private},
    }


def make_health_check(hc_id="hc-abc123", hc_type="HTTPS", fqdn="api.example.com"):
    return {
        "Id": hc_id,
        "HealthCheckConfig": {
            "Type": hc_type,
            "FullyQualifiedDomainName": fqdn,
            "Port": 443,
            "ResourcePath": "/health",
        },
    }


@pytest.fixture
def collector():
    session = MagicMock()
    r53 = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: r53 if svc == "route53" else cw
    c = Route53Collector(session, "global", "TT-0001")
    c._r53 = r53
    c._cw = cw
    return c, r53, cw


class TestRoute53Collector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "route53"

    def test_no_zones_no_health_checks_returns_empty(self, collector):
        c, r53, cw = collector
        r53.get_paginator.return_value.paginate.return_value = [
            {"HostedZones": []},
        ]
        # Both calls to get_paginator return empty
        r53.get_paginator.return_value.paginate.side_effect = [
            [{"HostedZones": []}],
            [{"HealthChecks": []}],
        ]
        assert c.collect() == []

    def test_hosted_zone_record_emitted(self, collector):
        c, r53, cw = collector
        r53.get_paginator.return_value.paginate.side_effect = [
            [{"HostedZones": [make_hosted_zone()]}],
            [{"HealthChecks": []}],
        ]
        records = c.collect()
        zone_recs = [r for r in records if r.metric_name == "record_set_count"]
        assert len(zone_recs) == 1
        assert zone_recs[0].metric_value == 15
        assert zone_recs[0].resource_name == "example.com"

    def test_private_zone_dimension(self, collector):
        c, r53, cw = collector
        r53.get_paginator.return_value.paginate.side_effect = [
            [{"HostedZones": [make_hosted_zone(private=True)]}],
            [{"HealthChecks": []}],
        ]
        records = c.collect()
        zone_rec = next(r for r in records if r.metric_name == "record_set_count")
        assert zone_rec.dimensions["private_zone"] == "True"

    def test_health_check_status_emitted(self, collector):
        c, r53, cw = collector
        r53.get_paginator.return_value.paginate.side_effect = [
            [{"HostedZones": []}],
            [{"HealthChecks": [make_health_check()]}],
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 1.0}]
        }
        records = c.collect()
        status_recs = [r for r in records if r.metric_name == "health_check_status"]
        assert len(status_recs) == 1
        assert status_recs[0].metric_value == "healthy"

    def test_health_check_unhealthy_when_zero(self, collector):
        c, r53, cw = collector
        r53.get_paginator.return_value.paginate.side_effect = [
            [{"HostedZones": []}],
            [{"HealthChecks": [make_health_check()]}],
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 0.0}]
        }
        records = c.collect()
        status_recs = [r for r in records if r.metric_name == "health_check_status"]
        assert status_recs[0].metric_value == "unhealthy"

    def test_client_error_returns_empty(self, collector):
        c, r53, _ = collector
        r53.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListHostedZones",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, r53, cw = collector
        r53.get_paginator.return_value.paginate.side_effect = [
            [{"HostedZones": [make_hosted_zone()]}],
            [{"HealthChecks": []}],
        ]
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
