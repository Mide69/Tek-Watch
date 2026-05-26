"""Unit tests for the CloudWatchAlarmsCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.cloudwatch_alarms import CloudWatchAlarmsCollector


def make_alarm(name="high-cpu", state="ALARM", metric="CPUUtilization", threshold=80.0):
    return {
        "AlarmName": name,
        "AlarmArn": f"arn:aws:cloudwatch:eu-west-1:123:alarm:{name}",
        "StateValue": state,
        "MetricName": metric,
        "Namespace": "AWS/EC2",
        "Threshold": threshold,
        "ComparisonOperator": "GreaterThanThreshold",
        "StateUpdatedTimestamp": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def collector():
    session = MagicMock()
    cw = MagicMock()
    session.client.return_value = cw
    c = CloudWatchAlarmsCollector(session, "eu-west-1", "TT-0001")
    c._cw = cw
    return c, cw


class TestCloudWatchAlarmsCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "cloudwatch_alarms"

    def test_no_alarms_returns_empty(self, collector):
        c, cw = collector
        cw.get_paginator.return_value.paginate.return_value = [{"MetricAlarms": []}]
        assert c.collect() == []

    def test_alarm_record_emitted(self, collector):
        c, cw = collector
        cw.get_paginator.return_value.paginate.return_value = [
            {"MetricAlarms": [make_alarm()]}
        ]
        records = c.collect()
        assert len(records) == 1
        assert records[0].metric_name == "alarm_state"
        assert records[0].metric_value == "ALARM"
        assert records[0].resource_name == "high-cpu"

    def test_alarm_arn_used_as_resource_id(self, collector):
        c, cw = collector
        cw.get_paginator.return_value.paginate.return_value = [
            {"MetricAlarms": [make_alarm()]}
        ]
        records = c.collect()
        assert "arn:aws:cloudwatch" in records[0].resource_id

    def test_multiple_alarms_all_emitted(self, collector):
        c, cw = collector
        alarms = [
            make_alarm("cpu-alarm", "ALARM"),
            make_alarm("mem-alarm", "OK"),
            make_alarm("disk-alarm", "INSUFFICIENT_DATA"),
        ]
        cw.get_paginator.return_value.paginate.return_value = [{"MetricAlarms": alarms}]
        records = c.collect()
        assert len(records) == 3
        states = {r.metric_value for r in records}
        assert states == {"ALARM", "OK", "INSUFFICIENT_DATA"}

    def test_alarm_dimensions_include_threshold(self, collector):
        c, cw = collector
        cw.get_paginator.return_value.paginate.return_value = [
            {"MetricAlarms": [make_alarm(threshold=90.0)]}
        ]
        records = c.collect()
        assert records[0].dimensions["threshold"] == 90.0
        assert records[0].dimensions["metric_name"] == "CPUUtilization"
        assert records[0].dimensions["namespace"] == "AWS/EC2"

    def test_paginated_alarms_all_collected(self, collector):
        c, cw = collector
        cw.get_paginator.return_value.paginate.return_value = [
            {"MetricAlarms": [make_alarm("a1")]},
            {"MetricAlarms": [make_alarm("a2"), make_alarm("a3")]},
        ]
        records = c.collect()
        assert len(records) == 3

    def test_client_error_returns_empty(self, collector):
        c, cw = collector
        cw.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "DescribeAlarms",
        )
        assert c.collect() == []

    def test_endpoint_error_returns_empty(self, collector):
        c, cw = collector
        cw.get_paginator.side_effect = EndpointResolutionError(msg="endpoint not available")
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, cw = collector
        cw.get_paginator.return_value.paginate.return_value = [
            {"MetricAlarms": [make_alarm()]}
        ]
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
