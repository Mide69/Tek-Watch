"""Unit tests for the admin audit log service."""
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError


@pytest.fixture
def mock_table():
    with patch("services.audit_log.boto3") as mock_boto3, \
         patch("services.audit_log.load_config") as mock_config:
        mock_config.return_value = MagicMock(dynamodb_audit_log_table="tek_watch_audit_log")
        table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = table
        yield table


class TestLogAction:
    def test_writes_required_fields(self, mock_table):
        from services.audit_log import log_action
        log_action("admin-sub-1", "customer.create")

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["admin_id"] == "admin-sub-1"
        assert item["action"] == "customer.create"
        assert "#" in item["sk"]  # timestamp#event_id format
        assert "timestamp" in item

    def test_includes_optional_fields_when_provided(self, mock_table):
        from services.audit_log import log_action
        log_action(
            "admin-sub-1",
            "customer.update",
            customer_id="TT-0001",
            details={"fields_changed": ["name"]},
            ip_address="1.2.3.4",
        )
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["customer_id"] == "TT-0001"
        assert item["details"] == {"fields_changed": ["name"]}
        assert item["ip_address"] == "1.2.3.4"

    def test_omits_optional_fields_when_not_provided(self, mock_table):
        from services.audit_log import log_action
        log_action("admin-sub-1", "customer.rotate_key")
        item = mock_table.put_item.call_args[1]["Item"]
        assert "customer_id" not in item
        assert "details" not in item
        assert "ip_address" not in item

    def test_swallows_client_error(self, mock_table):
        from services.audit_log import log_action
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "no table"}},
            "PutItem",
        )
        # Should not raise
        log_action("admin-sub-1", "customer.create")

    def test_swallows_generic_exception(self, mock_table):
        from services.audit_log import log_action
        mock_table.put_item.side_effect = RuntimeError("boom")
        log_action("admin-sub-1", "customer.create")


class TestGetRecentActions:
    def test_returns_items_sorted_descending(self, mock_table):
        from services.audit_log import get_recent_actions
        mock_table.query.return_value = {
            "Items": [
                {"admin_id": "admin-1", "sk": "2026-06-16T10:00:00#abc", "action": "customer.create"},
            ]
        }
        result = get_recent_actions("admin-1", limit=10)
        assert len(result) == 1
        kwargs = mock_table.query.call_args[1]
        assert kwargs["ScanIndexForward"] is False
        assert kwargs["Limit"] == 10

    def test_returns_empty_list_on_error(self, mock_table):
        from services.audit_log import get_recent_actions
        mock_table.query.side_effect = RuntimeError("boom")
        result = get_recent_actions("admin-1")
        assert result == []
