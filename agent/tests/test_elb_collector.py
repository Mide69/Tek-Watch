"""Unit tests for the ELBCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.elb import ELBCollector


def make_alb(
    name="prod-alb",
    arn="arn:aws:elasticloadbalancing:eu-west-1:123:loadbalancer/app/prod-alb/abc",
    state="active",
    lb_type="application",
):
    return {
        "LoadBalancerArn": arn,
        "LoadBalancerName": name,
        "Type": lb_type,
        "State": {"Code": state},
        "Scheme": "internet-facing",
        "VpcId": "vpc-abc",
    }


def make_classic_lb(name="classic-lb"):
    return {
        "LoadBalancerName": name,
        "Scheme": "internet-facing",
        "VPCId": "vpc-abc",
    }


@pytest.fixture
def collector():
    session = MagicMock()
    elbv2 = MagicMock()
    elb = MagicMock()
    cw = MagicMock()

    def client_factory(svc, **kw):
        if svc == "elbv2":
            return elbv2
        if svc == "elb":
            return elb
        return cw

    session.client.side_effect = client_factory
    c = ELBCollector(session, "eu-west-1", "TT-0001")
    c._elbv2 = elbv2
    c._elb = elb
    c._cw = cw
    return c, elbv2, elb, cw


class TestELBCollector:
    def test_service_name(self, collector):
        c, _, _, _ = collector
        assert c.SERVICE_NAME == "elb"

    def test_no_lbs_returns_empty(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [{"LoadBalancers": []}]
        elb.get_paginator.return_value.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        assert c.collect() == []

    def test_alb_state_emitted(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [
            {"LoadBalancers": [make_alb()]}
        ]
        elb.get_paginator.return_value.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_recs = [r for r in records if r.metric_name == "load_balancer_state"]
        assert any(r.resource_name == "prod-alb" for r in state_recs)
        assert any(r.metric_value == "active" for r in state_recs)

    def test_inactive_alb_skips_cw(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [
            {"LoadBalancers": [make_alb(state="provisioning")]}
        ]
        elb.get_paginator.return_value.paginate.return_value = [{"LoadBalancerDescriptions": []}]

        records = c.collect()
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_cw_metric_emitted_for_active_alb(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [
            {"LoadBalancers": [make_alb()]}
        ]
        elb.get_paginator.return_value.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Sum": 1500.0}]
        }

        records = c.collect()
        assert len(records) > 1

    def test_nlb_uses_network_namespace(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [
            {"LoadBalancers": [make_alb(lb_type="network")]}
        ]
        elb.get_paginator.return_value.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_recs = [r for r in records if r.metric_name == "load_balancer_state"]
        assert len(state_recs) >= 1
        assert state_recs[0].dimensions["type"] == "network"

    def test_classic_elb_emitted(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [{"LoadBalancers": []}]
        elb.get_paginator.return_value.paginate.return_value = [
            {"LoadBalancerDescriptions": [make_classic_lb()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        classic_recs = [r for r in records if r.metric_name == "load_balancer_state"]
        assert len(classic_recs) == 1
        assert classic_recs[0].resource_name == "classic-lb"

    def test_customer_id_propagated(self, collector):
        c, elbv2, elb, cw = collector
        elbv2.get_paginator.return_value.paginate.return_value = [
            {"LoadBalancers": [make_alb()]}
        ]
        elb.get_paginator.return_value.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
