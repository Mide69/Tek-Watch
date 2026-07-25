"""DynamoDB service — customer, alert, and threshold CRUD."""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DynamoDBService:
    """Handles all DynamoDB operations for customers, alerts, and thresholds."""

    def __init__(self) -> None:
        config = load_config()
        self._resource = boto3.resource("dynamodb", region_name=config.aws_region)
        self._customers = self._resource.Table(config.dynamodb_customers_table)
        self._alerts = self._resource.Table(config.dynamodb_alerts_table)
        self._thresholds = self._resource.Table(config.dynamodb_thresholds_table)

    # ── Customers ─────────────────────────────────────────────────────────────

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a customer profile by ID."""
        try:
            response = self._customers.get_item(
                Key={"customer_id": customer_id, "SK": "PROFILE"}
            )
            return response.get("Item")
        except ClientError as exc:
            logger.error("get_customer failed for %s: %s", customer_id, exc)
            return None

    def list_customers(self) -> List[Dict[str, Any]]:
        """Scan all customer profiles (admin only)."""
        try:
            response = self._customers.scan(
                FilterExpression="SK = :sk",
                ExpressionAttributeValues={":sk": "PROFILE"},
            )
            return response.get("Items", [])
        except ClientError as exc:
            logger.error("list_customers failed: %s", exc)
            return []

    def create_customer(
        self,
        name: str,
        email: str,
        subscription_tier: str,
        aws_account_ids: List[str],
    ) -> Dict[str, Any]:
        """Create a new customer. Generates Customer ID and API key.

        Returns:
            Dict with customer_id, api_key (plaintext, shown once), and profile.
        """
        # Generate sequential Customer ID
        customer_id = self._generate_customer_id()
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        item = {
            "customer_id": customer_id,
            "SK": "PROFILE",
            "name": name,
            "email": email,
            "subscription_tier": subscription_tier,
            "aws_account_ids": aws_account_ids,
            "api_key_hash": api_key_hash,
            "status": "active",
            "agent_status": "unknown",
            "created_at": _now_iso(),
            "last_agent_seen": None,
        }

        self._customers.put_item(Item=item)
        logger.info("Customer created: %s", customer_id)
        return {"customer_id": customer_id, "api_key": api_key, "profile": item}

    def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> bool:
        """Update allowed customer fields."""
        allowed = {"name", "email", "subscription_tier", "aws_account_ids", "status"}
        safe_updates = {k: v for k, v in updates.items() if k in allowed}
        if not safe_updates:
            return False

        expr = "SET " + ", ".join(f"#{k} = :{k}" for k in safe_updates)
        names = {f"#{k}": k for k in safe_updates}
        values = {f":{k}": v for k, v in safe_updates.items()}

        try:
            self._customers.update_item(
                Key={"customer_id": customer_id, "SK": "PROFILE"},
                UpdateExpression=expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
            return True
        except ClientError as exc:
            logger.error("update_customer failed for %s: %s", customer_id, exc)
            return False

    def rotate_api_key(self, customer_id: str) -> Optional[str]:
        """Generate a new API key for a customer. Returns plaintext key."""
        new_key = secrets.token_urlsafe(32)
        new_hash = hashlib.sha256(new_key.encode()).hexdigest()
        try:
            self._customers.update_item(
                Key={"customer_id": customer_id, "SK": "PROFILE"},
                UpdateExpression="SET api_key_hash = :h",
                ExpressionAttributeValues={":h": new_hash},
            )
            return new_key
        except ClientError as exc:
            logger.error("rotate_api_key failed for %s: %s", customer_id, exc)
            return None

    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer profile. Used to roll back a failed signup —
        not exposed via any admin endpoint (customers are deactivated via
        status, not deleted, once they have real data)."""
        try:
            self._customers.delete_item(Key={"customer_id": customer_id, "SK": "PROFILE"})
            return True
        except ClientError as exc:
            logger.error("delete_customer failed for %s: %s", customer_id, exc)
            return False

    def update_agent_heartbeat(self, customer_id: str, status: str = "healthy") -> None:
        """Update last_agent_seen and agent_status for a customer."""
        try:
            self._customers.update_item(
                Key={"customer_id": customer_id, "SK": "PROFILE"},
                UpdateExpression="SET last_agent_seen = :t, agent_status = :s",
                ExpressionAttributeValues={":t": _now_iso(), ":s": status},
            )
        except ClientError as exc:
            logger.warning("update_agent_heartbeat failed for %s: %s", customer_id, exc)

    def _generate_customer_id(self) -> str:
        """Generate next sequential Customer ID in TT-XXXX format."""
        customers = self.list_customers()
        if not customers:
            return "TT-0001"
        existing_ids = [c.get("customer_id", "") for c in customers]
        numbers = []
        for cid in existing_ids:
            if cid.startswith("TT-") and cid[3:].isdigit():
                numbers.append(int(cid[3:]))
        next_num = max(numbers, default=0) + 1
        return f"TT-{next_num:04d}"

    # ── Alerts ────────────────────────────────────────────────────────────────

    def get_alerts(
        self, customer_id: str, status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get alerts for a customer, optionally filtered by status."""
        try:
            response = self._alerts.query(
                KeyConditionExpression="customer_id = :cid",
                ExpressionAttributeValues={":cid": customer_id},
                ScanIndexForward=False,  # newest first
            )
            items = response.get("Items", [])
            if status_filter:
                items = [i for i in items if i.get("status") == status_filter]
            return items
        except ClientError as exc:
            logger.error("get_alerts failed for %s: %s", customer_id, exc)
            return []

    def create_alert(self, customer_id: str, alert_data: Dict[str, Any]) -> str:
        """Create a new alert record. Returns the alert_id."""
        import ulid
        alert_id = str(ulid.new())
        item = {
            "customer_id": customer_id,
            "SK": alert_id,
            "alert_id": alert_id,
            "status": "active",
            "triggered_at": _now_iso(),
            **alert_data,
        }
        try:
            self._alerts.put_item(Item=item)
            return alert_id
        except ClientError as exc:
            logger.error("create_alert failed for %s: %s", customer_id, exc)
            return ""

    def acknowledge_alert(self, customer_id: str, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        try:
            self._alerts.update_item(
                Key={"customer_id": customer_id, "SK": alert_id},
                UpdateExpression="SET #s = :s, acknowledged_at = :t",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "acknowledged",
                    ":t": _now_iso(),
                },
            )
            return True
        except ClientError as exc:
            logger.error("acknowledge_alert failed: %s", exc)
            return False

    # ── Thresholds ────────────────────────────────────────────────────────────

    def get_thresholds(self, customer_id: str = "DEFAULT") -> List[Dict[str, Any]]:
        """Get thresholds for a customer or the defaults."""
        try:
            response = self._thresholds.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": customer_id},
            )
            return response.get("Items", [])
        except ClientError as exc:
            logger.error("get_thresholds failed for %s: %s", customer_id, exc)
            return []

    def upsert_threshold(
        self, customer_id: str, service: str, metric_name: str, config: Dict[str, Any]
    ) -> bool:
        """Create or update a threshold."""
        sk = f"{service}#{metric_name}"
        try:
            self._thresholds.put_item(Item={
                "PK": customer_id,
                "SK": sk,
                "service": service,
                "metric_name": metric_name,
                **config,
            })
            return True
        except ClientError as exc:
            logger.error("upsert_threshold failed: %s", exc)
            return False
