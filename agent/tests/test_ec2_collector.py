"""Unit tests for the EC2Collector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from collectors.ec2 import EC2Collector


def make_instance(instance_id="i-abc123", state="running", instance_type="t3.medium"):
    return {
        "InstanceId": instance_id,
        "InstanceType": instance_type,
        "State": {"Name": state},
        "Placement": {"AvailabilityZone": "eu-west-1a"},
        "VpcId": "vpc-123",
        "SubnetId": "subnet-456",
        "Tags": [{"Key": "Name", "Value": "web-server"}],
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ec2_client = MagicMock()
    cw_client = MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        ec2_client if svc == "ec2" else cw_client
    )
    c = EC2Collector(session, "eu-west-1", "TT-0001")
    c._ec2 = ec2_client
    c._cw = cw_client
    return c, ec2_client, cw_client


class TestEC2Collector:
    def test_collect_returns_inventory_record(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [make_instance()]}]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inventory = [r for r in records if r.metric_name == "instance_state"]
        assert len(inventory) == 1
        assert inventory[0].metric_value == "running"
        assert inventory[0].resource_id == "i-abc123"
        assert inventory[0].resource_name == "web-server"

    def test_collect_stopped_instance_no_cw_metrics(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [make_instance(state="stopped")]}]}
        ]
        records = c.collect()
        # Only inventory record, no CloudWatch metrics
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_collect_running_instance_fetches_cw_metrics(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [make_instance()]}]}
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 73.4}]
        }
        records = c.collect()
        cpu_records = [r for r in records if r.metric_name == "cpu_utilization_percent"]
        assert len(cpu_records) == 1
        assert cpu_records[0].metric_value == 73.4

    def test_collect_no_instances_returns_empty(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": []}
        ]
        records = c.collect()
        assert records == []

    def test_collect_handles_client_error_gracefully(self, collector):
        from botocore.exceptions import ClientError
        c, ec2, cw = collector
        ec2.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DescribeInstances"
        )
        records = c.collect()
        assert records == []

    def test_dimensions_include_instance_type_and_az(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [make_instance()]}]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = records[0]
        assert inv.dimensions["instance_type"] == "t3.medium"
        assert inv.dimensions["az"] == "eu-west-1a"

    def test_service_name_is_ec2(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "ec2"

    def test_customer_id_propagated(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [make_instance()]}]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)

    def test_cw_metric_missing_datapoints_skipped(self, collector):
        c, ec2, cw = collector
        ec2.get_paginator.return_value.paginate.return_value = [
            {"Reservations": [{"Instances": [make_instance()]}]}
        ]
        # All CW calls return empty datapoints
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        # Only inventory record, no metric records
        metric_records = [r for r in records if r.metric_name != "instance_state"]
        assert metric_records == []
