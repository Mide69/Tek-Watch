"""Unit tests for the SQS Collector."""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from collectors.sqs import SQSCollector


QUEUE_URL = "https://sqs.eu-west-2.amazonaws.com/123456789012/my-queue"
DLQ_URL   = "https://sqs.eu-west-2.amazonaws.com/123456789012/my-queue-dlq"


def make_attrs(visible=42, inflight=5, age=120):
    return {
        "Attributes": {
            "QueueArn":                              f"arn:aws:sqs:eu-west-2:123:{QUEUE_URL.split('/')[-1]}",
            "ApproximateNumberOfMessages":           str(visible),
            "ApproximateNumberOfMessagesNotVisible": str(inflight),
            "ApproximateAgeOfOldestMessage":         str(age),
        }
    }


@pytest.fixture
def collector():
    session    = MagicMock()
    sqs_client = MagicMock()
    session.client.return_value = sqs_client
    c = SQSCollector(session, "eu-west-2", "TT-0001")
    c._sqs = sqs_client
    return c, sqs_client


class TestSQSCollector:
    def test_collect_returns_records_for_each_queue(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value         = {"QueueUrls": [QUEUE_URL]}
        sqs.get_queue_attributes.return_value = make_attrs()
        records = c.collect()
        assert len(records) > 0

    def test_visible_messages_metric(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value         = {"QueueUrls": [QUEUE_URL]}
        sqs.get_queue_attributes.return_value = make_attrs(visible=99)
        records = c.collect()
        vis = [r for r in records if r.metric_name == "approximate_number_of_messages_visible"]
        assert vis[0].metric_value == 99.0

    def test_inflight_messages_metric(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value         = {"QueueUrls": [QUEUE_URL]}
        sqs.get_queue_attributes.return_value = make_attrs(inflight=7)
        records = c.collect()
        inf = [r for r in records if r.metric_name == "messages_in_flight"]
        assert inf[0].metric_value == 7.0

    def test_oldest_message_age_metric(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value         = {"QueueUrls": [QUEUE_URL]}
        sqs.get_queue_attributes.return_value = make_attrs(age=300)
        records = c.collect()
        age = [r for r in records if r.metric_name == "approximate_age_of_oldest_message_seconds"]
        assert age[0].metric_value == 300.0

    def test_no_queues_returns_empty(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value = {"QueueUrls": []}
        assert c.collect() == []

    def test_list_queues_error_returns_empty(self, collector):
        c, sqs = collector
        sqs.list_queues.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "no"}}, "ListQueues"
        )
        assert c.collect() == []

    def test_get_attributes_error_skips_queue(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value = {"QueueUrls": [QUEUE_URL, DLQ_URL]}
        sqs.get_queue_attributes.side_effect = [
            ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "GetQueueAttributes"),
            make_attrs(),
        ]
        records = c.collect()
        assert len(records) > 0   # second queue still collected

    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "sqs"

    def test_customer_id_propagated(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value         = {"QueueUrls": [QUEUE_URL]}
        sqs.get_queue_attributes.return_value = make_attrs()
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)

    def test_resource_name_derived_from_url(self, collector):
        c, sqs = collector
        sqs.list_queues.return_value         = {"QueueUrls": [QUEUE_URL]}
        sqs.get_queue_attributes.return_value = make_attrs()
        records = c.collect()
        assert all(r.resource_name == "my-queue" for r in records)
