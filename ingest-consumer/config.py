"""Ingest consumer configuration — reads from environment and Secrets Manager."""
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConsumerConfig:
    """Immutable ingest consumer configuration."""

    aws_region: str
    environment: str
    sqs_ingest_queue_url: str
    dynamodb_metrics_table: str
    dynamodb_events_table: str
    dynamodb_customers_table: str
    log_level: str


@lru_cache(maxsize=1)
def load_config() -> ConsumerConfig:
    """Load config from environment variables and AWS Secrets Manager.

    Raises:
        SystemExit: If required config is missing or Secrets Manager is unreachable.
    """
    aws_region = os.environ.get("AWS_REGION", "eu-west-2")
    environment = os.environ.get("ENVIRONMENT", "dev")
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    secret_arn = os.environ.get("SECRETS_MANAGER_SECRET_ARN", "")

    secrets: dict = {}
    if secret_arn:
        try:
            sm = boto3.client("secretsmanager", region_name=aws_region)
            response = sm.get_secret_value(SecretId=secret_arn)
            secrets = json.loads(response["SecretString"])
        except ClientError as exc:
            logger.critical("Failed to load secrets from Secrets Manager: %s", exc)
            raise SystemExit(1) from exc
    else:
        # Local dev fallback — read directly from env
        secrets = {
            "sqs_ingest_queue_url": os.environ.get("SQS_INGEST_QUEUE_URL", ""),
            "dynamodb_metrics_table": os.environ.get("DYNAMODB_METRICS_TABLE", "tek_watch_metrics"),
            "dynamodb_events_table": os.environ.get("DYNAMODB_EVENTS_TABLE", "tek_watch_events"),
            "dynamodb_customers_table": os.environ.get(
                "DYNAMODB_CUSTOMERS_TABLE", "tek_watch_customers"
            ),
        }

    return ConsumerConfig(
        aws_region=aws_region,
        environment=environment,
        sqs_ingest_queue_url=secrets.get("sqs_ingest_queue_url", ""),
        dynamodb_metrics_table=secrets.get("dynamodb_metrics_table", "tek_watch_metrics"),
        dynamodb_events_table=secrets.get("dynamodb_events_table", "tek_watch_events"),
        dynamodb_customers_table=secrets.get("dynamodb_customers_table", "tek_watch_customers"),
        log_level=log_level,
    )
