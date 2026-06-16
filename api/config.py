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
    # DynamoDB
    dynamodb_customers_table: str
    dynamodb_alerts_table: str
    dynamodb_thresholds_table: str
    dynamodb_usage_table: str
    dynamodb_audit_log_table: str
    # Metrics/events (replaces Timestream — closed to new AWS accounts 2025-06-20)
    dynamodb_metrics_table: str
    dynamodb_events_table: str
    # Cognito
    cognito_customer_user_pool_id: str
    cognito_customer_app_client_id: str
    cognito_admin_user_pool_id: str
    cognito_admin_app_client_id: str
    # Anthropic
    anthropic_api_key: str
    # SNS / SES
    sns_ops_alerts_topic_arn: str
    ses_from_email: str
    # Slack
    slack_webhook_url: str
    # SQS
    sqs_ingest_queue_url: str
    # CORS — comma-separated allowed origins
    allowed_origins: str


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
            "dynamodb_customers_table",
            "dynamodb_alerts_table", "dynamodb_thresholds_table",
            "dynamodb_usage_table", "dynamodb_audit_log_table",
            "dynamodb_metrics_table", "dynamodb_events_table",
            "cognito_customer_user_pool_id", "cognito_customer_app_client_id",
            "cognito_admin_user_pool_id", "cognito_admin_app_client_id",
            "anthropic_api_key", "sns_ops_alerts_topic_arn", "ses_from_email",
            "slack_webhook_url", "sqs_ingest_queue_url", "allowed_origins",
        ]}
        # Sensible local defaults
        secrets.setdefault("dynamodb_customers_table", "tek_watch_customers")
        secrets.setdefault("dynamodb_alerts_table", "tek_watch_alerts")
        secrets.setdefault("dynamodb_thresholds_table", "tek_watch_thresholds")
        secrets.setdefault("dynamodb_usage_table", "tek_watch_usage")
        secrets.setdefault("dynamodb_audit_log_table", "tek_watch_audit_log")
        secrets.setdefault("dynamodb_metrics_table", "tek_watch_metrics")
        secrets.setdefault("dynamodb_events_table", "tek_watch_events")

    return APIConfig(
        aws_region=aws_region,
        environment=environment,
        log_level=log_level,
        dynamodb_customers_table=secrets.get("dynamodb_customers_table", "tek_watch_customers"),
        dynamodb_alerts_table=secrets.get("dynamodb_alerts_table", "tek_watch_alerts"),
        dynamodb_thresholds_table=secrets.get("dynamodb_thresholds_table", "tek_watch_thresholds"),
        dynamodb_usage_table=secrets.get("dynamodb_usage_table", "tek_watch_usage"),
        dynamodb_audit_log_table=secrets.get("dynamodb_audit_log_table", "tek_watch_audit_log"),
        dynamodb_metrics_table=secrets.get("dynamodb_metrics_table", "tek_watch_metrics"),
        dynamodb_events_table=secrets.get("dynamodb_events_table", "tek_watch_events"),
        cognito_customer_user_pool_id=secrets.get("cognito_customer_user_pool_id", ""),
        cognito_customer_app_client_id=secrets.get("cognito_customer_app_client_id", ""),
        cognito_admin_user_pool_id=secrets.get("cognito_admin_user_pool_id", ""),
        cognito_admin_app_client_id=secrets.get("cognito_admin_app_client_id", ""),
        anthropic_api_key=secrets.get("anthropic_api_key", ""),
        sns_ops_alerts_topic_arn=secrets.get("sns_ops_alerts_topic_arn", ""),
        ses_from_email=secrets.get("ses_from_email", ""),
        slack_webhook_url=secrets.get("slack_webhook_url", ""),
        sqs_ingest_queue_url=secrets.get("sqs_ingest_queue_url", ""),
        allowed_origins=secrets.get(
            "allowed_origins",
            "http://localhost:3000,http://localhost:3001,"
            "https://app.tekwatch.io,https://admin.tekwatch.io,"
            "https://dev.tekwatch.io,https://staging.tekwatch.io",
        ),
    )
