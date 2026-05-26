"""
Agent configuration — reads from environment variables only.
Never call os.environ directly in business logic; always use this module.
"""
import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Immutable agent configuration loaded from environment variables."""

    customer_id: str
    ingest_queue_url: str
    api_key: str
    log_level: str
    aws_region: str


def load_config() -> AgentConfig:
    """Load and validate agent configuration from environment variables.

    Raises:
        SystemExit: If any required environment variable is missing.
    """
    required = {
        "TEK_WATCH_CUSTOMER_ID": os.environ.get("TEK_WATCH_CUSTOMER_ID", ""),
        "TEK_WATCH_INGEST_QUEUE_URL": os.environ.get("TEK_WATCH_INGEST_QUEUE_URL", ""),
        "TEK_WATCH_API_KEY": os.environ.get("TEK_WATCH_API_KEY", ""),
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        logging.critical("Missing required environment variables: %s", ", ".join(missing))
        raise SystemExit(1)

    return AgentConfig(
        customer_id=required["TEK_WATCH_CUSTOMER_ID"],
        ingest_queue_url=required["TEK_WATCH_INGEST_QUEUE_URL"],
        api_key=required["TEK_WATCH_API_KEY"],
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        aws_region=os.environ.get("AWS_REGION", "eu-west-2"),
    )
