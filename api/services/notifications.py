"""Notification service — SNS ops alerts."""
import asyncio
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends alert notifications via SNS.

    All boto3 calls are run in a thread pool executor to avoid blocking
    the asyncio event loop.
    """

    def __init__(self) -> None:
        config = load_config()
        self._sns = boto3.client("sns", region_name=config.aws_region)
        self._ops_topic_arn = config.sns_ops_alerts_topic_arn

    async def send_ops_alert(
        self,
        customer_id: str,
        service: str,
        resource_id: str,
        metric_name: str,
        severity: str,
        current_value: Optional[float] = None,
        threshold_value: Optional[float] = None,
        description: Optional[str] = None,
    ) -> None:
        """Publish an alert to the Tek Watch ops SNS topic.

        Runs the boto3 call in a thread pool to avoid blocking the event loop.
        """
        if not self._ops_topic_arn:
            logger.debug("SNS ops topic not configured — skipping notification")
            return

        subject = f"[{severity.upper()}] Tek Watch Alert: {customer_id}"

        if description:
            message = (
                f"Customer: {customer_id}\n"
                f"Service: {service}\n"
                f"Resource: {resource_id}\n"
                f"Type: AI Anomaly\n"
                f"Severity: {severity.upper()}\n\n"
                f"{description}"
            )
        else:
            cv = f"{current_value:.4f}" if current_value is not None else "N/A"
            message = (
                f"Customer: {customer_id}\n"
                f"Service: {service}\n"
                f"Resource: {resource_id}\n"
                f"Metric: {metric_name}\n"
                f"Current Value: {cv}\n"
                f"Threshold: {threshold_value}\n"
                f"Severity: {severity.upper()}"
            )

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._sns.publish(
                    TopicArn=self._ops_topic_arn,
                    Subject=subject[:100],
                    Message=message,
                    MessageAttributes={
                        "severity":    {"DataType": "String", "StringValue": severity},
                        "customer_id": {"DataType": "String", "StringValue": customer_id},
                    },
                ),
            )
            logger.info(
                "Ops alert sent: customer=%s service=%s metric=%s severity=%s",
                customer_id, service, metric_name, severity,
            )
        except ClientError as exc:
            logger.error("SNS publish failed: %s", exc)
