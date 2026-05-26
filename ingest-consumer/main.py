"""
Tek Watch Ingest Consumer — long-running SQS poll loop.

Polls the ingest SQS queue, validates messages, writes to Timestream,
and deletes successfully processed messages.
"""
import logging
import signal
import sys
import time
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from config import load_config
from processor import MessageProcessor
from writer import TimestreamWriter

logger = logging.getLogger(__name__)

_RUNNING = True
_LONG_POLL_SECONDS = 20
_MAX_MESSAGES = 10


def _handle_signal(signum: int, frame: Any) -> None:
    global _RUNNING
    logger.info("Shutdown signal received (%s), draining...", signum)
    _RUNNING = False


def configure_logging(level: str) -> None:
    """Configure structured JSON logging."""
    import json
    from datetime import datetime, timezone

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            return json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            })

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers = [handler]


def process_messages(
    messages: List[Dict],
    processor: MessageProcessor,
    writer: TimestreamWriter,
    sqs: Any,
    queue_url: str,
) -> tuple[int, int]:
    """Process a batch of SQS messages.

    Returns:
        Tuple of (processed_count, failed_count).
    """
    processed = 0
    failed = 0
    to_delete: List[Dict[str, str]] = []

    for message in messages:
        body = message.get("Body", "")
        attrs = message.get("MessageAttributes", {})
        receipt = message.get("ReceiptHandle", "")
        msg_id = message.get("MessageId", "")

        record = processor.process(body, attrs)
        if record is None:
            # Invalid message — do NOT delete, let it go to DLQ after retries
            logger.warning("Message %s failed validation — leaving for DLQ", msg_id)
            failed += 1
            continue

        written = writer.write_batch([record])
        if written > 0:
            to_delete.append({"Id": msg_id, "ReceiptHandle": receipt})
            processed += 1
        else:
            logger.warning("Timestream write failed for message %s", msg_id)
            failed += 1

    # Batch delete successfully processed messages
    if to_delete:
        try:
            sqs.delete_message_batch(QueueUrl=queue_url, Entries=to_delete)
        except ClientError as exc:
            logger.error("SQS delete_message_batch failed: %s", exc)

    return processed, failed


def run() -> None:
    """Main consumer loop."""
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    config = load_config()
    configure_logging(config.log_level)

    logger.info(
        "Ingest consumer starting: env=%s queue=%s",
        config.environment,
        config.sqs_ingest_queue_url,
    )

    if not config.sqs_ingest_queue_url:
        logger.critical("SQS_INGEST_QUEUE_URL not configured — exiting")
        sys.exit(1)

    sqs = boto3.client("sqs", region_name=config.aws_region)
    processor = MessageProcessor(
        dynamodb_table_name=config.dynamodb_customers_table,
        aws_region=config.aws_region,
    )
    writer = TimestreamWriter(
        database_name=config.timestream_database_name,
        metrics_table=config.timestream_metrics_table,
        events_table=config.timestream_events_table,
        aws_region=config.aws_region,
    )

    total_processed = 0
    total_failed = 0

    while _RUNNING:
        try:
            response = sqs.receive_message(
                QueueUrl=config.sqs_ingest_queue_url,
                MaxNumberOfMessages=_MAX_MESSAGES,
                WaitTimeSeconds=_LONG_POLL_SECONDS,
                MessageAttributeNames=["All"],
                AttributeNames=["All"],
            )
            messages = response.get("Messages", [])

            if not messages:
                continue

            processed, failed = process_messages(
                messages, processor, writer, sqs, config.sqs_ingest_queue_url
            )
            total_processed += processed
            total_failed += failed

            logger.info(
                "Batch complete: processed=%d failed=%d total_processed=%d total_failed=%d",
                processed,
                failed,
                total_processed,
                total_failed,
            )

        except ClientError as exc:
            logger.error("SQS receive_message failed: %s", exc)
            time.sleep(5)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error in consumer loop: %s", exc)
            time.sleep(5)

    logger.info(
        "Consumer stopped. total_processed=%d total_failed=%d",
        total_processed,
        total_failed,
    )


if __name__ == "__main__":
    run()
