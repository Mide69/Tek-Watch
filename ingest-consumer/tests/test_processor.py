"""Unit tests for the ingest consumer MessageProcessor."""
import hashlib
import json
import pytest
from unittest.mock import MagicMock, patch
from processor import MessageProcessor, ValidatedRecord, REQUIRED_FIELDS


def make_valid_body(customer_id: str = "TT-0001") -> str:
    return json.dumps({
        "customer_id": customer_id,
        "collection_timestamp": "2026-01-01T00:00:00+00:00",
        "region": "eu-west-1",
        "service": "ec2",
        "resource_id": "i-abc123",
        "metric_name": "cpu_utilization_percent",
        "metric_value": 42.5,
        "unit": "percent",
        "resource_type": "instance",
        "resource_name": "web-server",
        "dimensions": {"az": "eu-west-1a"},
    })


def make_api_key_attrs(api_key: str) -> dict:
    return {"api_key": {"StringValue": api_key}}


def make_customer_item(customer_id: str, api_key: str) -> dict:
    return {
        "customer_id": customer_id,
        "SK": "PROFILE",
        "status": "active",
        "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest(),
    }


@pytest.fixture
def processor():
    with patch("processor.boto3") as mock_boto3:
        mock_table = MagicMock()
        mock_boto3.resource.return_value.Table.return_value = mock_table
        proc = MessageProcessor("tribe_watch_customers", "eu-west-2")
        proc._table = mock_table
        return proc, mock_table


class TestMessageProcessor:
    def test_valid_message_returns_record(self, processor):
        proc, table = processor
        api_key = "test-key-abc"
        table.get_item.return_value = {
            "Item": make_customer_item("TT-0001", api_key)
        }
        result = proc.process(make_valid_body(), make_api_key_attrs(api_key))
        assert isinstance(result, ValidatedRecord)
        assert result.customer_id == "TT-0001"
        assert result.service == "ec2"
        assert result.metric_value == 42.5

    def test_invalid_json_returns_none(self, processor):
        proc, _ = processor
        result = proc.process("not-json{{{", {})
        assert result is None

    def test_missing_required_field_returns_none(self, processor):
        proc, table = processor
        api_key = "test-key"
        table.get_item.return_value = {"Item": make_customer_item("TT-0001", api_key)}
        body = json.loads(make_valid_body())
        del body["metric_name"]
        result = proc.process(json.dumps(body), make_api_key_attrs(api_key))
        assert result is None

    def test_unknown_customer_returns_none(self, processor):
        proc, table = processor
        table.get_item.return_value = {}  # No Item key
        result = proc.process(make_valid_body(), make_api_key_attrs("any-key"))
        assert result is None

    def test_wrong_api_key_returns_none(self, processor):
        proc, table = processor
        table.get_item.return_value = {
            "Item": make_customer_item("TT-0001", "correct-key")
        }
        result = proc.process(make_valid_body(), make_api_key_attrs("wrong-key"))
        assert result is None

    def test_customer_cache_avoids_duplicate_dynamo_calls(self, processor):
        proc, table = processor
        api_key = "test-key"
        table.get_item.return_value = {"Item": make_customer_item("TT-0001", api_key)}
        attrs = make_api_key_attrs(api_key)
        proc.process(make_valid_body(), attrs)
        proc.process(make_valid_body(), attrs)
        # DynamoDB should only be called once due to cache
        assert table.get_item.call_count == 1

    def test_verify_api_key_correct(self):
        key = "my-secret-key"
        hashed = hashlib.sha256(key.encode()).hexdigest()
        assert MessageProcessor._verify_api_key(key, hashed) is True

    def test_verify_api_key_wrong(self):
        assert MessageProcessor._verify_api_key("wrong", "abc123") is False

    def test_verify_api_key_empty(self):
        assert MessageProcessor._verify_api_key("", "abc") is False
        assert MessageProcessor._verify_api_key("key", "") is False

    def test_all_required_fields_present(self):
        body = json.loads(make_valid_body())
        assert REQUIRED_FIELDS.issubset(set(body.keys()))
