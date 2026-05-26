"""SQS publisher — batches MetricRecords and sends to the ingest queue."""
import json
import logging
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import MetricRecord

logger = logging.getLogger(__name__)

_SQS_BATCH_SIZE = 10  # SQS send_message_batch maximum


class SQSPublisher:
    """Publishes MetricRecord objects to an SQS queue in batches of 10.

    Args:
        session: boto3 Session with credentials for the Tek Watch central account.
        queue_url: The SQS queue URL to publish to.
        api_key: The customer's agent API key (sent as a message attribute).
    """

    def __init__(self, session: boto3.Session, queue_url: str, api_key: str) -> None:
        self._sqs = session.client("sqs")
        self._queue_url = queue_url
        self._api_key = api_key

    def publish_batch(self, records: List[MetricRecord]) -> int:
        """Publish all records to SQS in batches of 10.

        Args:
            records: List of MetricRecord objects to publish.

        Returns:
            Number of records successfully published.

        Raises:
            SystemExit: If SQS publish fails completely (non-recoverable).
        """
        if not records:
            logger.info("No records to publish")
            return 0

        published = 0
        failed = 0

        for i in range(0, len(records), _SQS_BATCH_SIZE):
            batch = records[i : i + _SQS_BATCH_SIZE]
            entries = [
                {
                    "Id": str(idx),
                    "MessageBody": json.dumps(record.to_dict()),
                    "MessageAttributes": {
                        "api_key": {
                            "StringValue": self._api_key,
                            "DataType": "String",
                        },
                        "customer_id": {
                            "StringValue": record.customer_id,
                            "DataType": "String",
                        },
                    },
                }
                for idx, record in enumerate(batch)
            ]

            try:
                response = self._sqs.send_message_batch(
                    QueueUrl=self._queue_url,
                    Entries=entries,
                )
                batch_published = len(response.get("Successful", []))
                batch_failed = len(response.get("Failed", []))
                published += batch_published
                failed += batch_failed

                if batch_failed:
                    for failure in response.get("Failed", []):
                        logger.error(
                            "SQS message failed: id=%s code=%s message=%s",
                            failure.get("Id"),
                            failure.get("Code"),
                            failure.get("Message"),
                        )

            except (ClientError, EndpointResolutionError) as exc:
                logger.critical(
                    "SQS publish failed for batch starting at index %d: %s", i, exc
                )
                raise SystemExit(1) from exc

        logger.info(
            "SQS publish complete: published=%d failed=%d total=%d",
            published,
            failed,
            len(records),
        )
        return published
