"""Unit tests for the VPCCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.vpc import VPCCollector


def make_vpc(vpc_id="vpc-abc123", state="available", is_default=False):
    return {
        "VpcId": vpc_id,
        "State": state,
        "CidrBlock": "10.0.0.0/16",
        "IsDefault": is_default,
        "Tags": [{"Key": "Name", "Value": "prod-vpc"}],
    }


def make_nat(ngw_id="nat-abc123", state="available", vpc_id="vpc-abc123"):
    return {
        "NatGatewayId": ngw_id,
        "State": state,
        "VpcId": vpc_id,
        "SubnetId": "subnet-123",
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ec2 = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        ec2 if svc == "ec2" else cw
    )
    c = VPCCollector(session, "eu-west-1", "TT-0001")
    c._ec2 = ec2
    c._cw = cw
    return c, ec2, cw


class TestVPCCollector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "vpc"

    def test_vpc_inventory_record_emitted(self, collector):
        c, ec2, cw = collector
        ec2.describe_vpcs.return_value = {"Vpcs": [make_vpc()]}
        ec2.describe_subnets.return_value = {"Subnets": []}
        ec2.get_paginator.return_value.paginate.return_value = [{"NatGateways": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        vpc_recs = [r for r in records if r.metric_name == "vpc_state"]
        assert len(vpc_recs) == 1
        assert vpc_recs[0].metric_value == "available"
        assert vpc_recs[0].resource_id == "vpc-abc123"
        assert vpc_recs[0].resource_name == "prod-vpc"

    def test_subnet_count_in_vpc_dimensions(self, collector):
        c, ec2, cw = collector
        ec2.describe_vpcs.return_value = {"Vpcs": [make_vpc()]}
        ec2.describe_subnets.return_value = {
            "Subnets": [
                {"VpcId": "vpc-abc123"},
                {"VpcId": "vpc-abc123"},
                {"VpcId": "other-vpc"},
            ]
        }
        ec2.get_paginator.return_value.paginate.return_value = [{"NatGateways": []}]

        records = c.collect()
        vpc_rec = next(r for r in records if r.metric_name == "vpc_state")
        assert vpc_rec.dimensions["subnet_count"] == 2

    def test_nat_gateway_inventory_emitted(self, collector):
        c, ec2, cw = collector
        ec2.describe_vpcs.return_value = {"Vpcs": []}
        ec2.describe_subnets.return_value = {"Subnets": []}
        ec2.get_paginator.return_value.paginate.return_value = [
            {"NatGateways": [make_nat()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        nat_recs = [r for r in records if r.metric_name == "nat_gateway_state"]
        assert len(nat_recs) == 1
        assert nat_recs[0].metric_value == "available"

    def test_non_available_nat_skips_cw(self, collector):
        c, ec2, cw = collector
        ec2.describe_vpcs.return_value = {"Vpcs": []}
        ec2.describe_subnets.return_value = {"Subnets": []}
        ec2.get_paginator.return_value.paginate.return_value = [
            {"NatGateways": [make_nat(state="deleting")]}
        ]

        records = c.collect()
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_nat_cw_bytes_metric_emitted(self, collector):
        c, ec2, cw = collector
        ec2.describe_vpcs.return_value = {"Vpcs": []}
        ec2.describe_subnets.return_value = {"Subnets": []}
        ec2.get_paginator.return_value.paginate.return_value = [
            {"NatGateways": [make_nat()]}
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Sum": 1024.0}]
        }

        records = c.collect()
        bytes_recs = [r for r in records if "bytes" in r.metric_name]
        assert len(bytes_recs) > 0

    def test_client_error_returns_empty(self, collector):
        c, ec2, _ = collector
        ec2.describe_vpcs.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "DescribeVpcs",
        )
        ec2.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "DescribeNatGateways",
        )
        records = c.collect()
        assert records == []

    def test_customer_id_propagated(self, collector):
        c, ec2, cw = collector
        ec2.describe_vpcs.return_value = {"Vpcs": [make_vpc()]}
        ec2.describe_subnets.return_value = {"Subnets": []}
        ec2.get_paginator.return_value.paginate.return_value = [{"NatGateways": []}]

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
