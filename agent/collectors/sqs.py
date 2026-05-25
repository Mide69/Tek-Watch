"""SQS queue metrics collector."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)

_ATTRS = [
    "ApproximateNumberOfMessages",
    "ApproximateNumberOfMessagesNotVisible",
    "ApproximateAgeOfOldestMessage",
]


class SQSCollector(BaseCollector):
    """Collects SQS queue inventory and depth metrics."""

    SERVICE_NAME = "sqs"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._sqs = session.client("sqs", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect SQS queue inventory and queue depth metrics."""
        records: List[MetricRecord] = []
        try:
            response = self._sqs.list_queues()
            for queue_url in response.get("QueueUrls", []):
                records.extend(self._collect_queue(queue_url))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("SQS collection failed in %s: %s", self.region, exc)
        return records

    def _collect_queue(self, queue_url: str) -> List[MetricRecord]:
        """Collect metrics for a single SQS queue."""
        records: List[MetricRecord] = []
        queue_name = queue_url.split("/")[-1]

        try:
            attrs_response = self._sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=_ATTRS + ["QueueArn"],
            )
            attrs = attrs_response.get("Attributes", {})
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("Failed to get attributes for queue %s: %s", queue_name, exc)
            return records

        queue_arn = attrs.get("QueueArn", queue_url)
        is_dlq = "dlq" in queue_name.lower() or "dead" in queue_name.lower()

        metric_map = {
            "ApproximateNumberOfMessages":          ("approximate_number_of_messages_visible", "count"),
            "ApproximateNumberOfMessagesNotVisible": ("messages_in_flight",                    "count"),
            "ApproximateAgeOfOldestMessage":         ("approximate_age_of_oldest_message_seconds", "seconds"),
        }

        for attr_name, (metric_name, unit) in metric_map.items():
            raw = attrs.get(attr_name)
            if raw is not None:
                records.append(self._make_record(
                    resource_type="queue",
                    resource_id=queue_arn,
                    resource_name=queue_name,
                    metric_name=metric_name,
                    metric_value=int(raw),
                    unit=unit,
                    dimensions={"is_dlq": str(is_dlq)},
                ))

        return records
