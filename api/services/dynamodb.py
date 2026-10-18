"""DynamoDB service — customer, alert, and threshold CRUD."""
import hashlib
import logging
import secrets
import uuid
from boto3.dynamodb.types import TypeSerializer
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)


class EvidenceReadError(RuntimeError):
    """An evidence read failed or was truncated; never treat it as an empty log."""



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
        profiles = []
        kwargs = {"FilterExpression": "SK = :sk", "ExpressionAttributeValues": {":sk": "PROFILE"}}
        while True:
            response = self._customers.scan(**kwargs)
            profiles.extend(response.get("Items", []))
            key = response.get("LastEvaluatedKey")
            if not key:
                return profiles
            kwargs["ExclusiveStartKey"] = key

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
            # The signup key is hashed on write and never shown to anyone, so
            # until this is set the customer has no usable agent key.
            "agent_key_issued_at": "",
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
            "city", "postcode", "country", "logo_key", "agent_key_issued_at",
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

    # ── Compliance evidence log ───────────────────────────────────────────────
    #
    # Kept in the customers table under EVIDENCE# keys rather than a table of
    # its own: the records are small, they are always read for one customer,
    # and a separate table would be one more thing to provision per
    # environment for no gain. EVIDENCE_HEAD holds the last sequence number and
    # hash so a writer never has to read the whole log to append to it.

    _EVIDENCE_PREFIX = "EVIDENCE#"
    _EVIDENCE_HEAD = "EVIDENCE_HEAD"

    def recheck_request(self, customer_id: str, control_id: str, now: str) -> str:
        """Keep a stable collection boundary across repeated verification requests."""
        key = {"customer_id": customer_id, "SK": "RECHECK#" + control_id}
        try:
            self._customers.put_item(Item={**key, "requested_at": now, "verified": False},
                                     ConditionExpression="attribute_not_exists(SK) OR verified = :yes",
                                     ExpressionAttributeValues={":yes": True})
            return now
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise EvidenceReadError("Cannot initiate recheck") from exc
            item = self._customers.get_item(Key=key, ConsistentRead=True).get("Item", {})
            if not item.get("requested_at"):
                raise EvidenceReadError("Cannot read recheck boundary")
            return item["requested_at"]

    def complete_recheck(self, customer_id: str, control_id: str, requested_at: str) -> None:
        self._customers.update_item(
            Key={"customer_id": customer_id, "SK": "RECHECK#" + control_id},
            UpdateExpression="SET verified = :yes",
            ConditionExpression="requested_at = :at",
            ExpressionAttributeValues={":yes": True, ":at": requested_at},
        )

    def evidence_head(self, customer_id: str) -> Dict[str, Any]:
        """The last entry's sequence and hash, or the starting point."""
        from services.evidence import GENESIS
        try:
            item = self._customers.get_item(
                Key={"customer_id": customer_id, "SK": self._EVIDENCE_HEAD}, ConsistentRead=True
            ).get("Item")
        except ClientError as exc:
            logger.error("Evidence head read failed for %s: %s", customer_id, exc)
            return {"seq": 0, "hash": GENESIS, "readable": False}
        if not item:
            return {"seq": 0, "hash": GENESIS, "readable": True}
        return {
            "seq": int(item.get("seq", 0)),
            "hash": str(item.get("hash", GENESIS)),
            "last_snapshot": item.get("last_snapshot"),
            "last_anchor_at": item.get("last_anchor_at"),
            "readable": True,
        }

    def append_evidence(
        self,
        customer_id: str,
        entry: Dict[str, Any],
        last_snapshot: Optional[Dict[str, Any]] = None,
        last_anchor_at: Optional[str] = None,
    ) -> bool:
        """Append one entry. Refuses to overwrite a sequence number already used.

        The condition is what makes the log append-only in practice: two writers
        racing for the same sequence means the loser is rejected rather than
        silently replacing an entry somebody may already have downloaded.
        """
        # Entry creation and compare-and-swap of its head must commit together.
        from services.evidence import GENESIS
        from services.evidence import canonical
        if len(canonical(entry).encode("utf-8")) > 350_000:
            logger.error("Evidence entry exceeds safe item size for %s; not written", customer_id)
            return False
        seq = int(entry["seq"])
        if seq < 1:
            return False
        serializer = TypeSerializer()
        def encode(values):
            # DynamoDB forbids Python floats, including nested assessment metrics.
            def normal(value):
                if isinstance(value, float):
                    return Decimal(str(value))
                if isinstance(value, dict):
                    return {k: normal(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [normal(v) for v in value]
                return value
            return {k: serializer.serialize(normal(v)) for k, v in values.items()}
        sets = ["#s = :seq", "#h = :hash", "updated_at = :now"]
        values = {":seq": seq, ":hash": entry["hash"], ":now": entry["recorded_at"],
                  ":prev_seq": seq - 1, ":prev_hash": entry["prev_hash"]}
        if last_snapshot is not None:
            sets.append("last_snapshot = :snapshot")
            values[":snapshot"] = last_snapshot
        if last_anchor_at is not None:
            sets.append("last_anchor_at = :anchored")
            values[":anchored"] = last_anchor_at
        condition = "#s = :prev_seq AND #h = :prev_hash"
        if seq == 1 and entry["prev_hash"] == GENESIS:
            condition = "attribute_not_exists(#s) OR (" + condition + ")"
        request = [
            {"Put": {"TableName": self._customers.name,
                     "Item": encode({"customer_id": customer_id, "SK": f"{self._EVIDENCE_PREFIX}{seq:012d}", **entry}),
                     "ConditionExpression": "attribute_not_exists(SK)"}},
            {"Update": {"TableName": self._customers.name,
                        "Key": encode({"customer_id": customer_id, "SK": self._EVIDENCE_HEAD}),
                        "UpdateExpression": "SET " + ", ".join(sets), "ConditionExpression": condition,
                        "ExpressionAttributeNames": {"#s": "seq", "#h": "hash"},
                        "ExpressionAttributeValues": encode(values)}}]
        try:
            client = getattr(self, "_transaction_client", None) or boto3.client("dynamodb", region_name=load_config().aws_region)
            client.transact_write_items(
                TransactItems=request,
                ClientRequestToken=str(uuid.uuid5(uuid.NAMESPACE_URL, customer_id + ":" + str(seq) + ":" + entry["hash"])),
            )
            return True
        except ClientError as exc:
            logger.warning("Evidence transaction rejected for %s sequence %s: %s", customer_id, seq, exc.response.get("Error", {}).get("Code"))
            return False

    def recover_evidence_head(self, customer_id: str, apply: bool = False) -> Dict[str, Any]:
        """Explicit recovery of a legacy non-atomic write, after full chain validation."""
        from services import evidence
        head = self.evidence_head(customer_id)
        if not head.get("readable", True):
            raise EvidenceReadError("Head unavailable")
        entries = self.all_evidence(customer_id)
        if not evidence.verify(entries)["intact"]:
            raise EvidenceReadError("Recovery requires a complete consistent chain")
        seq = int(head.get("seq", 0))
        if seq > len(entries) or (seq and head["hash"] != entries[seq - 1]["hash"]):
            raise EvidenceReadError("Stored head conflicts with available history")
        if not entries or seq == len(entries):
            return {"recovery_needed": False, "seq": seq}
        snapshots = [e for e in entries if e["kind"] == evidence.SNAPSHOT]
        anchors = [e for e in entries if e["kind"] == evidence.ANCHOR]
        new_head = {"seq": entries[-1]["seq"], "hash": entries[-1]["hash"]}
        if apply:
            snapshot = snapshots[-1] if snapshots else None
            self._customers.update_item(
                Key={"customer_id": customer_id, "SK": self._EVIDENCE_HEAD},
                UpdateExpression="SET #s = :s, #h = :h, last_snapshot = :snapshot, last_anchor_at = :anchor",
                ConditionExpression="(#s = :old AND #h = :oldhash) OR attribute_not_exists(#s)",
                ExpressionAttributeNames={"#s": "seq", "#h": "hash"},
                ExpressionAttributeValues={":s": new_head["seq"], ":h": new_head["hash"], ":old": seq,
                                           ":oldhash": head["hash"],
                                           ":snapshot": {k: snapshot[k] for k in ("seq", "recorded_at", "body")} if snapshot else None,
                                           ":anchor": anchors[-1]["recorded_at"] if anchors else None},
            )
        return {"recovery_needed": True, "applied": apply, **new_head}

    def list_evidence(self, customer_id: str, limit: int = 50, newest_first: bool = True) -> List[Dict[str, Any]]:
        """Entries for one customer, newest first by default."""
        try:
            response = self._customers.query(
                KeyConditionExpression=Key("customer_id").eq(customer_id)
                & Key("SK").begins_with(self._EVIDENCE_PREFIX),
                ScanIndexForward=not newest_first,
                Limit=max(1, min(limit, 500)),
            )
        except ClientError as exc:
            logger.error("Evidence list failed for %s: %s", customer_id, exc)
            return []
        return [self._evidence_item(i) for i in response.get("Items", [])]

    def all_evidence(self, customer_id: str, cap: Optional[int] = None) -> List[Dict[str, Any]]:
        """Every entry, oldest first. Used to verify the chain end to end."""
        entries: List[Dict[str, Any]] = []
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": Key("customer_id").eq(customer_id)
            & Key("SK").begins_with(self._EVIDENCE_PREFIX),
            "ScanIndexForward": True,
            "ConsistentRead": True,
        }
        while True:
            try:
                response = self._customers.query(**kwargs)
            except ClientError as exc:
                raise EvidenceReadError("Evidence read unavailable") from exc
            entries.extend(self._evidence_item(i) for i in response.get("Items", []))
            if cap is not None and len(entries) > cap:
                raise EvidenceReadError("Evidence read exceeds explicit limit")
            key = response.get("LastEvaluatedKey")
            if not key:
                break
            kwargs["ExclusiveStartKey"] = key
        return entries

    @staticmethod
    def _evidence_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """Strip the table's own keys, and turn DynamoDB numbers back into ints."""
        entry = {k: v for k, v in item.items() if k not in ("customer_id", "SK")}
        if "seq" in entry:
            entry["seq"] = int(entry["seq"])
        return entry

    # ── Thresholds ────────────────────────────────────────────────────────────

    def get_baseline(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """The stored 7-day baseline, or None if there isn't a usable one.

        Computing it reads a week of every metric — 133,626 rows for the first
        real customer, which pinned a 0.25 vCPU task at 100% for minutes and
        got it replaced as unhealthy. Storing it means that work happens a few
        times a day instead of on every pass, and survives a task restart.
        """
        try:
            item = self._customers.get_item(
                Key={"customer_id": customer_id, "SK": "BASELINE"}
            ).get("Item")
        except ClientError as exc:
            logger.error("Baseline read failed for %s: %s", customer_id, exc)
            return None
        if not item:
            return None
        return {
            "computed_at": item.get("computed_at"),
            "series": [
                {
                    "service": s.get("service"),
                    "resource_id": s.get("resource_id"),
                    "metric_name": s.get("metric_name"),
                    "avg_value": float(s.get("avg_value", 0)),
                    "stddev_value": float(s.get("stddev_value", 0)),
                    "samples": int(s.get("samples", 0)),
                    "first_time": s.get("first_time"),
                }
                for s in item.get("series", [])
            ],
        }

    def put_baseline(self, customer_id: str, series: List[Dict[str, Any]]) -> None:
        """Store a freshly computed baseline. Never fatal: it is a cache."""
        if not series:
            return
        try:
            self._customers.put_item(Item={
                "customer_id": customer_id,
                "SK": "BASELINE",
                "computed_at": _now_iso(),
                "series": [
                    {
                        "service": s.get("service"),
                        "resource_id": s.get("resource_id"),
                        "metric_name": s.get("metric_name"),
                        "avg_value": Decimal(str(round(float(s.get("avg_value", 0)), 6))),
                        "stddev_value": Decimal(str(round(float(s.get("stddev_value", 0)), 6))),
                        "samples": int(s.get("samples", 0)),
                        "first_time": s.get("first_time"),
                    }
                    for s in series
                ],
            })
        except ClientError as exc:
            # Too big for one item, or throttled. Detection still works, it
            # just recomputes next pass.
            logger.warning("Baseline not stored for %s: %s", customer_id, exc)

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
