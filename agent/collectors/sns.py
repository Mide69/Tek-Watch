"""SNS topic inventory and metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class SNSCollector(BaseCollector):
    """Collects SNS topic inventory and CloudWatch delivery metrics."""

    SERVICE_NAME = "sns"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._sns = session.client("sns", region_name=region)
        self._cw  = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect SNS topic inventory and 24h delivery metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._sns.get_paginator("list_topics")
            for page in paginator.paginate():
                for topic in page.get("Topics", []):
                    records.extend(self._collect_topic(topic.get("TopicArn", "")))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("SNS collection failed in %s: %s", self.region, exc)
        return records

    def _collect_topic(self, topic_arn: str) -> List[MetricRecord]:
        """Collect metrics for a single SNS topic."""
        records: List[MetricRecord] = []
        topic_name = topic_arn.split(":")[-1]
        is_fifo = topic_name.endswith(".fifo")

        # Topic attributes
        subscriptions_confirmed = 0
        try:
            attrs = self._sns.get_topic_attributes(TopicArn=topic_arn).get("Attributes", {})
            subscriptions_confirmed = int(attrs.get("SubscriptionsConfirmed", 0))
        except (ClientError, EndpointResolutionError):
            pass

        base_dims = {
            "is_fifo":                  str(is_fifo),
            "subscriptions_count":      subscriptions_confirmed,
        }

        records.append(self._make_record(
            resource_type="topic",
            resource_id=topic_arn,
            resource_name=topic_name,
            metric_name="topic_state",
            metric_value="active",
            unit="none",
            dimensions=base_dims,
        ))

        end_time   = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)

        for cw_name, metric_name in [
            ("NumberOfMessagesPublished",       "messages_published_24h"),
            ("NumberOfNotificationsDelivered",  "messages_delivered_24h"),
            ("NumberOfNotificationsFailed",     "notifications_failed_24h"),
        ]:
            try:
                resp = self._cw.get_metric_statistics(
                    Namespace="AWS/SNS",
                    MetricName=cw_name,
                    Dimensions=[{"Name": "TopicName", "Value": topic_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=86400,
                    Statistics=["Sum"],
                )
                pts = resp.get("Datapoints", [])
                total = sum(d.get("Sum", 0) for d in pts)
                records.append(self._make_record(
                    resource_type="topic",
                    resource_id=topic_arn,
                    resource_name=topic_name,
                    metric_name=metric_name,
                    metric_value=int(total),
                    unit="count",
                    dimensions=base_dims,
                ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.debug("CW %s failed for SNS %s: %s", cw_name, topic_name, exc)

        return records
