"""Unit tests for the Timestream writer."""
import pytest
from unittest.mock import MagicMock, patch
from processor import ValidatedRecord
from writer import TimestreamWriter


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


@pytest.fixture
def writer():
    with patch("writer.boto3") as mock_boto3:
        mock_ts = MagicMock()
        mock_boto3.client.return_value = mock_ts
        w = TimestreamWriter("tek-watch", "metrics", "events", "eu-west-2")
        w._ts = mock_ts
        return w, mock_ts


class TestTimestreamWriter:
    def test_write_empty_returns_zero(self, writer):
        w, ts = writer
        result = w.write_batch([])
        assert result == 0
        ts.write_records.assert_not_called()

    def test_numeric_records_go_to_metrics_table(self, writer):
        w, ts = writer
        ts.write_records.return_value = {}
        records = [make_record(42.5)]
        w.write_batch(records)
        call_args = ts.write_records.call_args
        assert call_args[1]["TableName"] == "metrics"

    def test_string_records_go_to_events_table(self, writer):
        w, ts = writer
        ts.write_records.return_value = {}
        record = make_record(metric_value="running")
        w.write_batch([record])
        call_args = ts.write_records.call_args
        assert call_args[1]["TableName"] == "events"

    def test_mixed_records_split_correctly(self, writer):
        w, ts = writer
        ts.write_records.return_value = {}
        records = [make_record(42.5), make_record("running")]
        w.write_batch(records)
        assert ts.write_records.call_count == 2
        tables_called = {c[1]["TableName"] for c in ts.write_records.call_args_list}
        assert tables_called == {"metrics", "events"}

    def test_rejected_records_handled_gracefully(self, writer):
        w, ts = writer
        # Must assign the CLASS to the mock attribute so the except clause resolves correctly
        RejectedRecordsExc = type("RejectedRecordsException", (Exception,), {})
        ts.exceptions.RejectedRecordsException = RejectedRecordsExc
        exc_instance = RejectedRecordsExc()
        exc_instance.response = {"RejectedRecords": [{"RecordIndex": 0}]}
        ts.write_records.side_effect = exc_instance
        records = [make_record(42.5)]
        # Should not raise; rejected count subtracted from written
        result = w.write_batch(records)
        assert result == 0

    def test_timestream_record_has_required_fields(self, writer):
        w, ts = writer
        ts.write_records.return_value = {}
        record = make_record(73.4)
        w.write_batch([record])
        ts_record = ts.write_records.call_args[1]["Records"][0]
        assert "Dimensions" in ts_record
        assert "MeasureName" in ts_record
        assert "MeasureValue" in ts_record
        assert "MeasureValueType" in ts_record
        assert "Time" in ts_record
        assert ts_record["MeasureValueType"] == "DOUBLE"

    def test_dimension_customer_id_always_present(self, writer):
        w, ts = writer
        ts.write_records.return_value = {}
        w.write_batch([make_record(1.0)])
        dims = {d["Name"]: d["Value"]
                for d in ts.write_records.call_args[1]["Records"][0]["Dimensions"]}
        assert dims["customer_id"] == "TT-0001"
        assert dims["service"] == "ec2"
        assert dims["region"] == "eu-west-1"

    def test_batch_size_limit_respected(self, writer):
        w, ts = writer
        ts.write_records.return_value = {}
        # 250 records → 3 batches of 100
        records = [make_record(float(i)) for i in range(250)]
        w.write_batch(records)
        assert ts.write_records.call_count == 3
