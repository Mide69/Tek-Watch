"""Unit tests for the DynamoDB metrics writer (replaces Timestream)."""
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from botocore.exceptions import ClientError
from processor import ValidatedRecord
from writer import MetricsWriter


def make_record(metric_value=42.5, service="ec2") -> ValidatedRecord:
    return ValidatedRecord(
        customer_id="TT-0001",
        collection_timestamp="2026-01-01T00:00:00+00:00",
        region="eu-west-1",
        service=service,
        resource_type="instance",
        resource_id="i-abc123",
        resource_name="web-server",
        metric_name="cpu_utilization_percent",
        metric_value=metric_value,
        unit="percent",
        dimensions={"az": "eu-west-1a"},
    )


def _mock_batch_writer(table_mock):
    """Wire up table.batch_writer() as a context manager, return the inner batch mock."""
    batch = MagicMock()
    table_mock.batch_writer.return_value.__enter__ = MagicMock(return_value=batch)
    table_mock.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
    return batch


@pytest.fixture
def writer():
    with patch("writer.boto3") as mock_boto3:
        mock_metrics_table = MagicMock()
        mock_events_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = lambda name: {
            "metrics": mock_metrics_table,
            "events": mock_events_table,
        }[name]
        mock_boto3.resource.return_value = mock_dynamodb

        w = MetricsWriter("metrics", "events", "eu-west-2")
        metrics_batch = _mock_batch_writer(mock_metrics_table)
        events_batch = _mock_batch_writer(mock_events_table)
        return w, mock_metrics_table, mock_events_table, metrics_batch, events_batch


class TestMetricsWriter:
    def test_write_empty_returns_zero(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        result = w.write_batch([])
        assert result == 0
        metrics_batch.put_item.assert_not_called()
        events_batch.put_item.assert_not_called()

    def test_numeric_records_go_to_metrics_table(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        result = w.write_batch([make_record(42.5)])
        assert result == 1
        metrics_batch.put_item.assert_called_once()
        events_batch.put_item.assert_not_called()

    def test_string_records_go_to_events_table(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        result = w.write_batch([make_record(metric_value="running")])
        assert result == 1
        events_batch.put_item.assert_called_once()
        metrics_batch.put_item.assert_not_called()

    def test_mixed_records_split_correctly(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        result = w.write_batch([make_record(42.5), make_record("running")])
        assert result == 2
        assert metrics_batch.put_item.call_count == 1
        assert events_batch.put_item.call_count == 1

    def test_write_failure_handled_gracefully(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        metrics_table.batch_writer.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "x"}},
            "BatchWriteItem",
        )
        # Should not raise
        result = w.write_batch([make_record(42.5)])
        assert result == 0

    def test_metric_item_has_required_fields(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        w.write_batch([make_record(73.4)])
        item = metrics_batch.put_item.call_args[1]["Item"]
        assert item["pk"] == "TT-0001#i-abc123#cpu_utilization_percent"
        assert item["time"] == "2026-01-01T00:00:00+00:00"
        assert item["value"] == Decimal("73.4")
        assert item["customer_id"] == "TT-0001"
        assert item["service"] == "ec2"
        assert item["region"] == "eu-west-1"
        assert "expires_at" in item
        assert item["dimensions"] == {"az": "eu-west-1a"}

    def test_event_item_has_required_fields(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        w.write_batch([make_record(metric_value="running")])
        item = events_batch.put_item.call_args[1]["Item"]
        assert item["pk"] == "TT-0001#ec2"
        assert item["sk"] == "2026-01-01T00:00:00+00:00#i-abc123#cpu_utilization_percent"
        assert item["value"] == "running"
        assert item["customer_id"] == "TT-0001"
        assert "expires_at" in item

    def test_customer_id_always_present(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        w.write_batch([make_record(1.0)])
        item = metrics_batch.put_item.call_args[1]["Item"]
        assert item["customer_id"] == "TT-0001"

    def test_many_records_all_written(self, writer):
        w, metrics_table, events_table, metrics_batch, events_batch = writer
        records = [make_record(float(i)) for i in range(250)]
        result = w.write_batch(records)
        assert result == 250
        assert metrics_batch.put_item.call_count == 250
