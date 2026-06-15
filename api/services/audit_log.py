"""Admin audit log — append-only log of admin actions to DynamoDB."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)


def _table():
    return boto3.resource("dynamodb").Table(load_config().dynamodb_audit_log_table)


def log_action(
    admin_id: str,
    action: str,
    *,
    customer_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Write an audit log entry. Silently swallows errors so it never breaks the caller.

    DynamoDB schema:
      PK  admin_id  (string)
      SK  {timestamp}#{event_id}  (string — sorts chronologically)
    """
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())[:8]
    item: dict[str, Any] = {
        "admin_id": admin_id,
        "sk": f"{now.isoformat()}#{event_id}",
        "action": action,
        "timestamp": now.isoformat(),
    }
    if customer_id:
        item["customer_id"] = customer_id
    if details:
        item["details"] = details
    if ip_address:
        item["ip_address"] = ip_address

    try:
        _table().put_item(Item=item)
    except ClientError as exc:
        logger.warning("Audit log write failed: %s", exc.response["Error"]["Code"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Audit log error: %s", exc)


def get_recent_actions(admin_id: str, limit: int = 50) -> list[dict]:
    """Return the most recent audit entries for an admin."""
    try:
        resp = _table().query(
            KeyConditionExpression="admin_id = :aid",
            ExpressionAttributeValues={":aid": admin_id},
            ScanIndexForward=False,
            Limit=limit,
        )
        return resp.get("Items", [])
    except Exception as exc:  # noqa: BLE001
        logger.debug("Audit log query error: %s", exc)
        return []
