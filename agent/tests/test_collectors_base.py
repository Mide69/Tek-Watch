"""Unit tests for the agent base collector and MetricRecord."""
import pytest
from unittest.mock import MagicMock
from collectors.base import BaseCollector, MetricRecord


class ConcreteCollector(BaseCollector):
    """Minimal concrete implementation for testing."""
    SERVICE_NAME = "test_service"

    def collect(self):
        return [
            self._make_record(
                resource_type="instance",
                resource_id="i-123",
                resource_name="test-instance",
                metric_name="cpu_utilization_percent",
                metric_value=42.5,
                unit="percent",
                dimensions={"az": "eu-west-1a"},
            )
        ]


@pytest.fixture
def collector():
    session = MagicMock()
    return ConcreteCollector(session, "eu-west-1", "TT-0001")


class TestMetricRecord:
    def test_to_dict_contains_all_fields(self):
        record = MetricRecord(
            customer_id="TT-0001",
            collection_timestamp="2026-01-01T00:00:00+00:00",
            region="eu-west-1",
            service="ec2",
            resource_type="instance",
            resource_id="i-abc",
            resource_name="web-server",
            metric_name="cpu_utilization_percent",
            metric_value=73.4,
            unit="percent",
            dimensions={"instance_type": "t3.medium"},
        )
        d = record.to_dict()
        assert d["customer_id"] == "TT-0001"
        assert d["service"] == "ec2"
        assert d["metric_value"] == 73.4
        assert d["dimensions"]["instance_type"] == "t3.medium"

    def test_to_dict_default_dimensions(self):
        record = MetricRecord(
            customer_id="TT-0001",
            collection_timestamp="2026-01-01T00:00:00+00:00",
            region="eu-west-1",
            service="ec2",
            resource_type="instance",
            resource_id="i-abc",
            resource_name="web",
            metric_name="state",
            metric_value="running",
            unit="none",
        )
        assert record.dimensions == {}


class TestBaseCollector:
    def test_make_record_fills_common_fields(self, collector):
        records = collector.collect()
        assert len(records) == 1
        r = records[0]
        assert r.customer_id == "TT-0001"
        assert r.region == "eu-west-1"
        assert r.service == "test_service"
        assert r.metric_value == 42.5
        assert r.dimensions["az"] == "eu-west-1a"

    def test_service_name_set(self, collector):
        assert collector.SERVICE_NAME == "test_service"

    def test_collection_timestamp_is_iso(self, collector):
        records = collector.collect()
        ts = records[0].collection_timestamp
        # Should be parseable as ISO 8601
        from datetime import datetime
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.year >= 2026
