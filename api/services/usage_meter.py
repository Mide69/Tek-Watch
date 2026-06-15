"""Usage metering — DynamoDB atomic counters per customer per month."""
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)


def _table():
    return boto3.resource("dynamodb").Table(load_config().dynamodb_usage_table)


def increment_api_call(
    customer_id: str,
    endpoint: str,
    *,
    region: str = "eu-west-2",
) -> None:
    """Atomically increment the API call counter for this customer + month.

    Silently swallows all errors so metering never breaks the request path.
    """
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        _table().update_item(
            Key={"customer_id": customer_id, "month": month},
            UpdateExpression=(
                "ADD api_calls :one, #ep :one "
                "SET last_seen = :ts, #r = if_not_exists(#r, :region)"
            ),
            ExpressionAttributeNames={
                "#ep": f"ep#{endpoint}",
                "#r": "region",
            },
            ExpressionAttributeValues={
                ":one": 1,
                ":ts": datetime.now(timezone.utc).isoformat(),
                ":region": region,
            },
        )
    except ClientError as exc:
        logger.debug("Usage metering skipped: %s", exc.response["Error"]["Code"])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Usage metering error: %s", exc)


def get_usage(customer_id: str, month: Optional[str] = None) -> dict:
    """Return usage record for customer + month (defaults to current month)."""
    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        resp = _table().get_item(Key={"customer_id": customer_id, "month": month})
        return resp.get("Item", {"customer_id": customer_id, "month": month, "api_calls": 0})
    except Exception as exc:  # noqa: BLE001
        logger.debug("Usage get error: %s", exc)
        return {"customer_id": customer_id, "month": month, "api_calls": 0}
