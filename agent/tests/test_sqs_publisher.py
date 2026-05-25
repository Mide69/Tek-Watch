"""Unit tests for the SQS publisher."""
import json
import pytest
from unittest.mock import MagicMock, patch, call
from collectors.base import MetricRecord
from publisher.sqs_publisher import SQSPublisher


def make_record(idx: int) -> MetricRecord:
    return MetricRecord(
        customer_id="TT-0001",
        collection_timestamp="2026-01-01T00:00:00+00:00",
        region="eu-west-1",
        service="ec2",
        resource_type="instance",
        resource_id=f"i-{idx:04d}",
        resource_name=f"instance-{idx}",
        metric_name="cpu_utilization_percent",
        metric_value=float(idx),
        unit="percent",
    )


@pytest.fixture
def mock_sqs():
    sqs = MagicMock()
    sqs.send_message_batch.return_value = {
        "Successful": [{"Id": str(i)} for i in range(10)],
        "Failed": [],
    }
    return sqs


@pytest.fixture
def publisher(mock_sqs):
    session = MagicMock()
    session.client.return_value = mock_sqs
    pub = SQSPublisher(session, "https://sqs.eu-west-2.amazonaws.com/123/queue", "test-key")
    pub._sqs = mock_sqs
    return pub, mock_sqs


class TestSQSPublisher:
    def test_publish_empty_returns_zero(self, publisher):
        pub, sqs = publisher
        result = pub.publish_batch([])
        assert result == 0
        sqs.send_message_batch.assert_not_called()

    def test_publish_single_batch(self, publisher):
        pub, sqs = publisher
        records = [make_record(i) for i in range(5)]
        sqs.send_message_batch.return_value = {
            "Successful": [{"Id": str(i)} for i in range(5)],
            "Failed": [],
        }
        result = pub.publish_batch(records)
        assert result == 5
        assert sqs.send_message_batch.call_count == 1

    def test_publish_batches_in_groups_of_10(self, publisher):
        pub, sqs = publisher
        records = [make_record(i) for i in range(25)]
        sqs.send_message_batch.return_value = {
            "Successful": [{"Id": str(i)} for i in range(10)],
            "Failed": [],
        }
        pub.publish_batch(records)
        # 25 records → 3 batches (10, 10, 5)
        assert sqs.send_message_batch.call_count == 3

    def test_message_body_is_valid_json(self, publisher):
        pub, sqs = publisher
        records = [make_record(0)]
        sqs.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}],
            "Failed": [],
        }
        pub.publish_batch(records)
        call_args = sqs.send_message_batch.call_args
        entries = call_args[1]["Entries"]
        body = json.loads(entries[0]["MessageBody"])
        assert body["customer_id"] == "TT-0001"
        assert body["service"] == "ec2"

    def test_api_key_in_message_attributes(self, publisher):
        pub, sqs = publisher
        records = [make_record(0)]
        sqs.send_message_batch.return_value = {
            "Successful": [{"Id": "0"}],
            "Failed": [],
        }
        pub.publish_batch(records)
        entries = sqs.send_message_batch.call_args[1]["Entries"]
        assert entries[0]["MessageAttributes"]["api_key"]["StringValue"] == "test-key"

    def test_failed_messages_logged(self, publisher):
        pub, sqs = publisher
        records = [make_record(0)]
        sqs.send_message_batch.return_value = {
            "Successful": [],
            "Failed": [{"Id": "0", "Code": "InternalError", "Message": "fail"}],
        }
        result = pub.publish_batch(records)
        assert result == 0
