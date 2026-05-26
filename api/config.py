"""API configuration — loaded from Secrets Manager at startup."""
import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class APIConfig:
    """Immutable API configuration."""

    aws_region: str
    environment: str
    log_level: str
    # Timestream
    timestream_database_name: str
    timestream_metrics_table: str
    timestream_events_table: str
    # DynamoDB
    dynamodb_customers_table: str
    dynamodb_alerts_table: str
    dynamodb_thresholds_table: str
    # Cognito
    cognito_customer_user_pool_id: str
    cognito_customer_app_client_id: str
    cognito_admin_user_pool_id: str
    cognito_admin_app_client_id: str
    # Anthropic
    anthropic_api_key: str
    # SNS / SES
    sns_ops_alerts_topic_arn: str
    # SQS
    sqs_ingest_queue_url: str


@lru_cache(maxsize=1)
def load_config() -> APIConfig:
    """Load config from Secrets Manager or environment (dev fallback).

    Raises:
        SystemExit: If Secrets Manager is unreachable in non-dev environments.
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
            logger.info("Loaded config from Secrets Manager")
        except ClientError as exc:
            logger.critical("Failed to load secrets: %s", exc)
            raise SystemExit(1) from exc
    else:
        # Local dev — read from environment
        secrets = {k: os.environ.get(k.upper(), "") for k in [
            "timestream_database_name", "timestream_metrics_table",
            "timestream_events_table", "dynamodb_customers_table",
            "dynamodb_alerts_table", "dynamodb_thresholds_table",
            "cognito_customer_user_pool_id", "cognito_customer_app_client_id",
            "cognito_admin_user_pool_id", "cognito_admin_app_client_id",
            "anthropic_api_key", "sns_ops_alerts_topic_arn", "sqs_ingest_queue_url",
        ]}
        # Sensible local defaults
        secrets.setdefault("timestream_database_name", "tek-watch")
        secrets.setdefault("timestream_metrics_table", "metrics")
        secrets.setdefault("timestream_events_table", "events")
        secrets.setdefault("dynamodb_customers_table", "tek_watch_customers")
        secrets.setdefault("dynamodb_alerts_table", "tek_watch_alerts")
        secrets.setdefault("dynamodb_thresholds_table", "tek_watch_thresholds")

    return APIConfig(
        aws_region=aws_region,
        environment=environment,
        log_level=log_level,
        timestream_database_name=secrets.get("timestream_database_name", "tek-watch"),
        timestream_metrics_table=secrets.get("timestream_metrics_table", "metrics"),
        timestream_events_table=secrets.get("timestream_events_table", "events"),
        dynamodb_customers_table=secrets.get("dynamodb_customers_table", "tek_watch_customers"),
        dynamodb_alerts_table=secrets.get("dynamodb_alerts_table", "tek_watch_alerts"),
        dynamodb_thresholds_table=secrets.get("dynamodb_thresholds_table", "tek_watch_thresholds"),
        cognito_customer_user_pool_id=secrets.get("cognito_customer_user_pool_id", ""),
        cognito_customer_app_client_id=secrets.get("cognito_customer_app_client_id", ""),
        cognito_admin_user_pool_id=secrets.get("cognito_admin_user_pool_id", ""),
        cognito_admin_app_client_id=secrets.get("cognito_admin_app_client_id", ""),
        anthropic_api_key=secrets.get("anthropic_api_key", ""),
        sns_ops_alerts_topic_arn=secrets.get("sns_ops_alerts_topic_arn", ""),
        sqs_ingest_queue_url=secrets.get("sqs_ingest_queue_url", ""),
    )
