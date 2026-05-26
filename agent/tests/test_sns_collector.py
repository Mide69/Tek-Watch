"""Unit tests for the SNSCollector."""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.sns import SNSCollector


def make_topic(arn="arn:aws:sns:eu-west-1:123:prod-alerts"):
    return {"TopicArn": arn}


@pytest.fixture
def collector():
    session = MagicMock()
    sns = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: sns if svc == "sns" else cw
    c = SNSCollector(session, "eu-west-1", "TT-0001")
    c._sns = sns
    c._cw = cw
    return c, sns, cw


class TestSNSCollector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "sns"

    def test_no_topics_returns_empty(self, collector):
        c, sns, _ = collector
        sns.get_paginator.return_value.paginate.return_value = [{"Topics": []}]
        assert c.collect() == []

    def test_topic_state_emitted(self, collector):
        c, sns, cw = collector
        sns.get_paginator.return_value.paginate.return_value = [
            {"Topics": [make_topic()]}
        ]
        sns.get_topic_attributes.return_value = {
            "Attributes": {"SubscriptionsConfirmed": "3"}
        }
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_recs = [r for r in records if r.metric_name == "topic_state"]
        assert len(state_recs) == 1
        assert state_recs[0].metric_value == "active"
        assert state_recs[0].resource_name == "prod-alerts"

    def test_subscriptions_count_in_dimensions(self, collector):
        c, sns, cw = collector
        sns.get_paginator.return_value.paginate.return_value = [
            {"Topics": [make_topic()]}
        ]
        sns.get_topic_attributes.return_value = {
            "Attributes": {"SubscriptionsConfirmed": "5"}
        }
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_rec = next(r for r in records if r.metric_name == "topic_state")
        assert state_rec.dimensions["subscriptions_count"] == 5

    def test_cw_delivery_metrics_emitted(self, collector):
        c, sns, cw = collector
        sns.get_paginator.return_value.paginate.return_value = [
            {"Topics": [make_topic()]}
        ]
        sns.get_topic_attributes.return_value = {"Attributes": {"SubscriptionsConfirmed": "1"}}
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Sum": 100.0}]
        }

        records = c.collect()
        delivery_recs = [r for r in records if "24h" in r.metric_name]
        assert len(delivery_recs) == 3
        metric_names = {r.metric_name for r in delivery_recs}
        assert "messages_published_24h" in metric_names
        assert "messages_delivered_24h" in metric_names
        assert "notifications_failed_24h" in metric_names

    def test_fifo_topic_detected(self, collector):
        c, sns, cw = collector
        sns.get_paginator.return_value.paginate.return_value = [
            {"Topics": [make_topic("arn:aws:sns:eu-west-1:123:my-topic.fifo")]}
        ]
        sns.get_topic_attributes.return_value = {"Attributes": {"SubscriptionsConfirmed": "0"}}
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_rec = next(r for r in records if r.metric_name == "topic_state")
        assert state_rec.dimensions["is_fifo"] == "True"

    def test_client_error_returns_empty(self, collector):
        c, sns, _ = collector
        sns.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListTopics",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, sns, cw = collector
        sns.get_paginator.return_value.paginate.return_value = [
            {"Topics": [make_topic()]}
        ]
        sns.get_topic_attributes.return_value = {"Attributes": {"SubscriptionsConfirmed": "0"}}
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
