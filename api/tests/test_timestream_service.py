"""Unit tests for TimestreamQueryService — now DynamoDB-backed.

Filename/class name kept for historical continuity (this service still
answers exactly the same "metric queries" call sites it always did — see
services/timestream.py's module docstring for why the storage backend
changed but the public interface didn't).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from unittest.mock import MagicMock, patch
from services.timestream import TimestreamQueryService, _safe, _SAFE_ID_RE, _SAFE_RANGE_RE


class TestSafeInputValidation:
    """Test the _safe() allowlist function — defense-in-depth now that
    DynamoDB's Key() condition builder is parameterized (not raw SQL)."""

    def test_valid_customer_id_passes(self):
        assert _safe("TT-0001") == "TT-0001"

    def test_valid_service_name_passes(self):
        assert _safe("ec2") == "ec2"
        assert _safe("cost_explorer") == "cost_explorer"
        assert _safe("cloudwatch_alarms") == "cloudwatch_alarms"

    def test_valid_resource_id_passes(self):
        assert _safe("i-0abc123def456") == "i-0abc123def456"

    def test_sql_injection_attempt_raises(self):
        with pytest.raises(ValueError):
            _safe("TT-0001' OR '1'='1")

    def test_newline_injection_raises(self):
        with pytest.raises(ValueError):
            _safe("TT-0001\nDROP TABLE metrics")

    def test_semicolon_injection_raises(self):
        with pytest.raises(ValueError):
            _safe("ec2; DROP TABLE metrics")

    def test_quote_injection_raises(self):
        with pytest.raises(ValueError):
            _safe("ec2'--")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            _safe("")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            _safe("a" * 65)

    def test_valid_time_ranges_pass(self):
        for r in ("24h", "7d", "30d", "90d", "5m", "1h"):
            assert _safe(r, _SAFE_RANGE_RE) == r

    def test_invalid_time_range_raises(self):
        with pytest.raises(ValueError):
            _safe("999d", _SAFE_RANGE_RE)

    def test_time_range_injection_raises(self):
        with pytest.raises(ValueError):
            _safe("24h; DROP TABLE", _SAFE_RANGE_RE)


class TestHelpers:
    def test_get_bin_size_30d(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("30d") == timedelta(hours=1)

    def test_get_bin_size_90d(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("90d") == timedelta(hours=6)

    def test_get_bin_size_24h_returns_none(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("24h") is None

    def test_get_bin_size_7d_returns_none(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("7d") is None

    def test_since_iso_returns_past_timestamp(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        since = datetime.fromisoformat(svc._since_iso("1h"))
        assert since < datetime.now(timezone.utc)

    def test_bin_average_groups_by_bucket(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [
            {"time": base.isoformat(), "value": "10"},
            {"time": (base + timedelta(minutes=10)).isoformat(), "value": "20"},
            {"time": (base + timedelta(hours=2)).isoformat(), "value": "100"},
        ]
        result = svc._bin_average(rows, timedelta(hours=1))
        assert len(result) == 2
        assert result[0]["value"] == 15.0  # avg of 10, 20 in the first hour bucket
        assert result[1]["value"] == 100.0

    def test_bin_average_empty_returns_empty(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._bin_average([], timedelta(hours=1)) == []


@pytest.fixture
def svc():
    with patch("services.timestream.boto3") as mock_boto3, \
         patch("services.timestream.load_config") as mock_config:
        mock_config.return_value = MagicMock(
            aws_region="eu-west-2",
            dynamodb_metrics_table="tek_watch_metrics",
            dynamodb_events_table="tek_watch_events",
        )
        mock_metrics_table = MagicMock()
        mock_events_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = lambda name: {
            "tek_watch_metrics": mock_metrics_table,
            "tek_watch_events": mock_events_table,
        }[name]
        mock_boto3.resource.return_value = mock_dynamodb

        s = TimestreamQueryService()
        return s, mock_metrics_table, mock_events_table


class TestGetLatestMetric:
    def test_returns_latest_value(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": [{"value": Decimal("73.4")}]}
        result = s.get_latest_metric("TT-0001", "ec2", "i-abc", "cpu_utilization_percent")
        assert result == 73.4
        kwargs = metrics_table.query.call_args[1]
        assert kwargs["ScanIndexForward"] is False
        assert kwargs["Limit"] == 1

    def test_no_data_returns_none(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": []}
        assert s.get_latest_metric("TT-0001", "ec2", "i-abc", "cpu") is None

    def test_client_error_returns_none(self, svc):
        from botocore.exceptions import ClientError
        s, metrics_table, _ = svc
        metrics_table.query.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "x"}}, "Query"
        )
        assert s.get_latest_metric("TT-0001", "ec2", "i-abc", "cpu") is None

    def test_rejects_injection_attempt(self, svc):
        s, _, _ = svc
        with pytest.raises(ValueError):
            s.get_latest_metric("TT-0001' OR 1=1--", "ec2", "i-abc", "cpu")


class TestGetTimeSeries:
    def test_raw_data_for_24h(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {
            "Items": [{"time": "2026-01-01T00:00:00+00:00", "value": Decimal("50")}]
        }
        result = s.get_time_series("TT-0001", "i-abc", "cpu", "24h")
        assert result == [{"time": "2026-01-01T00:00:00+00:00", "value": 50.0}]

    def test_30d_returns_binned_data(self, svc):
        s, metrics_table, _ = svc
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        metrics_table.query.return_value = {
            "Items": [
                {"time": base.isoformat(), "value": Decimal("10")},
                {"time": (base + timedelta(minutes=30)).isoformat(), "value": Decimal("20")},
            ]
        }
        result = s.get_time_series("TT-0001", "i-abc", "cpu", "30d")
        assert len(result) == 1
        assert result[0]["value"] == 15.0

    def test_rejects_bad_time_range(self, svc):
        s, _, _ = svc
        with pytest.raises(ValueError):
            s.get_time_series("TT-0001", "i-abc", "cpu", "999d")

    def test_paginates_through_all_pages(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.side_effect = [
            {
                "Items": [{"time": "2026-01-01T00:00:00+00:00", "value": Decimal("1")}],
                "LastEvaluatedKey": {"pk": "x", "time": "y"},
            },
            {"Items": [{"time": "2026-01-01T01:00:00+00:00", "value": Decimal("2")}]},
        ]
        result = s.get_time_series("TT-0001", "i-abc", "cpu", "24h")
        assert len(result) == 2
        assert metrics_table.query.call_count == 2


class TestGetResourcesByService:
    def test_returns_rows_from_events_table(self, svc):
        s, _, events_table = svc
        events_table.query.return_value = {
            "Items": [{
                "resource_id": "i-abc", "resource_name": "web",
                "metric_name": "instance_state", "value": "running",
                "time": "2026-01-01T00:00:00+00:00",
            }]
        }
        result = s.get_resources_by_service("TT-0001", "ec2")
        assert len(result) == 1
        assert result[0]["value"] == "running"

    def test_rejects_bad_range(self, svc):
        s, _, _ = svc
        with pytest.raises(ValueError):
            s.get_resources_by_service("TT-0001", "ec2", "999d")

    def test_client_error_returns_empty_list(self, svc):
        from botocore.exceptions import ClientError
        s, _, events_table = svc
        events_table.query.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "x"}}, "Query"
        )
        assert s.get_resources_by_service("TT-0001", "ec2") == []


class TestAnomalyDetectionQueries:
    def test_get_7day_summary_groups_and_aggregates(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {
            "Items": [
                {"service": "ec2", "resource_id": "i-abc", "metric_name": "cpu", "value": Decimal("10")},
                {"service": "ec2", "resource_id": "i-abc", "metric_name": "cpu", "value": Decimal("20")},
            ]
        }
        result = s.get_7day_summary("TT-0001")
        assert len(result) == 1
        assert result[0]["avg_value"] == 15.0
        assert result[0]["stddev_value"] > 0
        # GSI is used for the broad customer-wide scan
        assert metrics_table.query.call_args[1]["IndexName"] == "gsi_customer_time"

    def test_get_7day_summary_single_value_has_zero_stddev(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {
            "Items": [{"service": "ec2", "resource_id": "i-abc", "metric_name": "cpu", "value": Decimal("10")}]
        }
        result = s.get_7day_summary("TT-0001")
        assert result[0]["stddev_value"] == 0.0

    def test_get_last_hour_returns_raw_rows(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {
            "Items": [{
                "service": "ec2", "resource_id": "i-abc", "metric_name": "cpu",
                "value": Decimal("42"), "time": "2026-01-01T00:00:00+00:00",
            }]
        }
        result = s.get_last_hour("TT-0001")
        assert result[0]["value"] == 42.0


class TestCostQueries:
    def test_get_daily_costs_filters_to_cost_explorer(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {
            "Items": [
                {"service": "cost_explorer", "metric_name": "daily_blended_cost",
                 "value": Decimal("12.5"), "time": "2026-01-01T00:00:00+00:00"},
                {"service": "ec2", "metric_name": "cpu", "value": Decimal("99"),
                 "time": "2026-01-01T00:00:00+00:00"},
            ]
        }
        result = s.get_daily_costs("TT-0001")
        assert len(result) == 1
        assert result[0]["cost"] == 12.5

    def test_get_service_costs_sorted_descending(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {
            "Items": [
                {"service": "cost_explorer", "metric_name": "mtd_blended_cost",
                 "resource_name": "EC2", "value": Decimal("50")},
                {"service": "cost_explorer", "metric_name": "mtd_blended_cost",
                 "resource_name": "S3", "value": Decimal("200")},
            ]
        }
        result = s.get_service_costs("TT-0001")
        assert result[0]["aws_service"] == "S3"
        assert result[0]["mtd_cost"] == 200.0
