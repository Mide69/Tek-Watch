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
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new customer. Generates Customer ID and API key.

        Returns:
            Dict with customer_id, api_key (plaintext, shown once), and profile.
        """
        # Random, non-sequential — see _generate_customer_id for why.
        customer_id = self._generate_customer_id()
        api_key = secrets.token_urlsafe(32)
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        def _build(cid: str) -> Dict[str, Any]:
            # Rebuilt per attempt rather than mutated: aliasing one dict across
            # retries makes the retry invisible to anything holding a reference.
            return {
            "customer_id": cid,
            "SK": "PROFILE",
            "name": name,
            "email": email,
            # Collected on the signup form since day one but never stored, so
            # every dashboard fell back to showing the raw Customer ID.
            "company_name": company or "",
            "phone": "",
            "website": "",
            "address_line1": "",
            "address_line2": "",
            "city": "",
            "postcode": "",
            "country": "",
            "logo_key": "",
            "subscription_tier": subscription_tier,
            "aws_account_ids": aws_account_ids,
            "api_key_hash": api_key_hash,
            "status": "active",
            "agent_status": "unknown",
            "created_at": _now_iso(),
            "last_agent_seen": None,
            }

        # Conditional: a generated id colliding with an existing customer must
        # fail rather than overwrite them. Retried with a fresh id — at ~10^12
        # combinations this should never fire, but "should never" is exactly how
        # the previous overwrite went unnoticed.
        for attempt in range(5):
            item = _build(customer_id)
            try:
                self._customers.put_item(
                    Item=item,
                    ConditionExpression="attribute_not_exists(customer_id)",
                )
                logger.info("Customer created: %s", customer_id)
                return {"customer_id": customer_id, "api_key": api_key, "profile": item}
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                    raise
                logger.warning("Customer id collision on %s, retrying", customer_id)
                customer_id = self._generate_customer_id()

        raise RuntimeError(f"Could not allocate a unique customer id after {attempt + 1} attempts")

    def update_customer(self, customer_id: str, updates: Dict[str, Any]) -> bool:
        """Update allowed customer fields."""
        allowed = {
            "name", "email", "subscription_tier", "aws_account_ids", "status",
            # Company profile, editable by the customer via PUT /api/v1/profile.
            "company_name", "phone", "website", "address_line1", "address_line2",
            "city", "postcode", "country", "logo_key",
        }
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

    # Crockford base32: no I, L, O or U, so nothing is misread as 1 or 0 when a
    # customer types their ID — it doubles as their Cognito username.
    _ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    _ID_LENGTH = 8

    def _generate_customer_id(self) -> str:
        """Generate a random, non-sequential Customer ID (TT-XXXXXXXX).

        Deliberately not sequential. The previous implementation scanned every
        customer, took the highest number and added one, which was wrong three
        ways:

        - Race: two concurrent signups both read the same maximum and both
          produced the same id. The write was unconditional, so the second
          silently overwrote the first, destroying that customer's record and
          api_key_hash while reporting success to both.
        - Enumerable: the id is also the Cognito username, so TT-0001, TT-0002
          and so on could be walked to discover accounts.
        - Disclosive: TT-0042 tells anyone roughly how many customers exist.

        8 characters from a 32-symbol alphabet is about 10^12 combinations, so
        collisions are vanishingly rare — and create_customer now writes
        conditionally, so even one cannot overwrite an existing customer.
        """
        suffix = "".join(secrets.choice(self._ID_ALPHABET) for _ in range(self._ID_LENGTH))
        return f"TT-{suffix}"

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

    def create_alert(
        self,
        customer_id: str,
        alert_data: Dict[str, Any],
        dedupe_key: Optional[str] = None,
    ) -> str:
        """Create a new alert record. Returns the alert_id, or "" if not created.

        Pass dedupe_key for alerts that represent an ongoing condition (a metric
        over threshold, say) rather than a point-in-time event. It makes the
        range key deterministic and the write conditional, so concurrent callers
        cannot both raise the same alert.

        That matters because callers check "is there already an active alert for
        this resource?" and then write, which is a read-then-write race: with
        api_desired_count above 1 — the default in variables.tf — two replicas
        evaluating the same threshold can both read "no alert", both write, and
        both notify. DynamoDB settles it here instead, atomically.

        The condition still allows a NEW alert once a previous one is resolved,
        which a plain attribute_not_exists would block forever.
        """
        if dedupe_key:
            alert_id = f"THRESHOLD#{dedupe_key}"
        else:
            # python-ulid (the pinned dependency) exposes a ULID class. The old
            # call here was ulid.new(), which belongs to the unrelated ulid-py
            # package, so this raised AttributeError for every alert created
            # without a dedupe key.
            from ulid import ULID
            alert_id = str(ULID())
        item = {
            "customer_id": customer_id,
            "SK": alert_id,
            "alert_id": alert_id,
            "status": "active",
            "triggered_at": _now_iso(),
            **alert_data,
        }
        kwargs: Dict[str, Any] = {"Item": item}
        if dedupe_key:
            kwargs.update(
                ConditionExpression="attribute_not_exists(SK) OR #st <> :active",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":active": "active"},
            )
        try:
            self._alerts.put_item(**kwargs)
            return alert_id
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # Someone else already raised this one. Not an error — returning
                # "" keeps the caller from sending a duplicate notification.
                logger.debug("alert already active for %s (%s)", customer_id, dedupe_key)
                return ""
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
