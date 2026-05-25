"""Unit tests for TimestreamQueryService — input validation and helpers."""
import pytest
from unittest.mock import MagicMock, patch
from services.timestream import TimestreamQueryService, _safe, _SAFE_ID_RE, _SAFE_RANGE_RE


class TestSafeInputValidation:
    """Test the _safe() allowlist function that prevents query injection."""

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


class TestTimestreamHelpers:
    def test_range_to_ago_mapping(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._range_to_ago("24h") == "24h"
        assert svc._range_to_ago("7d") == "7d"
        assert svc._range_to_ago("30d") == "30d"
        assert svc._range_to_ago("90d") == "90d"
        assert svc._range_to_ago("unknown") == "24h"  # default

    def test_get_bin_size_30d(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("30d") == "1h"

    def test_get_bin_size_90d(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("90d") == "6h"

    def test_get_bin_size_24h_returns_none(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("24h") is None

    def test_get_bin_size_7d_returns_none(self):
        svc = TimestreamQueryService.__new__(TimestreamQueryService)
        assert svc._get_bin_size("7d") is None


class TestTimestreamQueryExecution:
    @pytest.fixture
    def svc(self):
        with patch("services.timestream.boto3") as mock_boto3:
            with patch("services.timestream.load_config") as mock_config:
                mock_config.return_value = MagicMock(
                    aws_region="eu-west-2",
                    timestream_database_name="tribe-watch",
                    timestream_metrics_table="metrics",
                    timestream_events_table="events",
                )
                mock_client = MagicMock()
                mock_boto3.client.return_value = mock_client
                s = TimestreamQueryService()
                s._client = mock_client
                return s, mock_client

    def test_run_query_returns_rows(self, svc):
        s, client = svc
        client.get_paginator.return_value.paginate.return_value = [{
            "ColumnInfo": [{"Name": "value"}, {"Name": "time"}],
            "Rows": [
                {"Data": [{"ScalarValue": "73.4"}, {"ScalarValue": "2026-01-01T00:00:00Z"}]},
            ],
        }]
        rows = s._run_query("SELECT 1")
        assert len(rows) == 1
        assert rows[0]["value"] == "73.4"

    def test_run_query_handles_client_error(self, svc):
        from botocore.exceptions import ClientError
        s, client = svc
        client.get_paginator.return_value.paginate.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "bad query"}},
            "Query"
        )
        rows = s._run_query("INVALID QUERY")
        assert rows == []

    def test_get_time_series_rejects_injection(self, svc):
        s, _ = svc
        with pytest.raises(ValueError):
            s.get_time_series("TT-0001' OR 1=1--", "i-abc", "cpu", "24h")

    def test_get_resources_by_service_rejects_bad_range(self, svc):
        s, _ = svc
        with pytest.raises(ValueError):
            s.get_resources_by_service("TT-0001", "ec2", "999d")
