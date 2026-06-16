"""Unit tests for the usage metering service."""
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError


@pytest.fixture
def mock_table():
    with patch("services.usage_meter.boto3") as mock_boto3, \
         patch("services.usage_meter.load_config") as mock_config:
        mock_config.return_value = MagicMock(dynamodb_usage_table="tek_watch_usage")
        table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = table
        yield table


class TestIncrementApiCall:
    def test_calls_update_item_with_atomic_add(self, mock_table):
        from services.usage_meter import increment_api_call
        increment_api_call("TT-0001", "overview")

        mock_table.update_item.assert_called_once()
        kwargs = mock_table.update_item.call_args[1]
        assert kwargs["Key"]["customer_id"] == "TT-0001"
        assert "ADD api_calls :one" in kwargs["UpdateExpression"]
        assert kwargs["ExpressionAttributeNames"]["#ep"] == "ep#overview"

    def test_swallows_client_error(self, mock_table):
        from services.usage_meter import increment_api_call
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "no table"}},
            "UpdateItem",
        )
        # Should not raise
        increment_api_call("TT-0001", "overview")

    def test_swallows_generic_exception(self, mock_table):
        from services.usage_meter import increment_api_call
        mock_table.update_item.side_effect = RuntimeError("boom")
        # Should not raise — metering must never break the request path
        increment_api_call("TT-0001", "overview")


class TestGetUsage:
    def test_returns_item_when_found(self, mock_table):
        from services.usage_meter import get_usage
        mock_table.get_item.return_value = {
            "Item": {"customer_id": "TT-0001", "month": "2026-06", "api_calls": 42}
        }
        result = get_usage("TT-0001", "2026-06")
        assert result["api_calls"] == 42

    def test_returns_zero_default_when_not_found(self, mock_table):
        from services.usage_meter import get_usage
        mock_table.get_item.return_value = {}
        result = get_usage("TT-0001", "2026-06")
        assert result["api_calls"] == 0
        assert result["customer_id"] == "TT-0001"

    def test_swallows_errors_and_returns_default(self, mock_table):
        from services.usage_meter import get_usage
        mock_table.get_item.side_effect = RuntimeError("boom")
        result = get_usage("TT-0001", "2026-06")
        assert result["api_calls"] == 0
