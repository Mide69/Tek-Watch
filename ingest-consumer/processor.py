"""
Message processor — validates SQS messages before writing to Timestream.

Validation steps:
  1. Parse JSON body
  2. Verify customer_id exists in DynamoDB
  3. Verify api_key matches stored hash
  4. Validate required fields
"""
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class ValidatedRecord:
    """A validated and parsed metric record ready for Timestream."""

    customer_id: str
    collection_timestamp: str
    region: str
    service: str
    resource_type: str
    resource_id: str
    resource_name: str
    metric_name: str
    metric_value: Any
    unit: str
    dimensions: Dict[str, Any]


REQUIRED_FIELDS = {
    "customer_id",
    "collection_timestamp",
    "region",
    "service",
    "resource_id",
    "metric_name",
    "metric_value",
}


class MessageProcessor:
    """Validates and transforms SQS messages into ValidatedRecord objects.

    Args:
        dynamodb_table_name: Name of the DynamoDB customers table.
        aws_region: AWS region for DynamoDB client.
    """

    def __init__(self, dynamodb_table_name: str, aws_region: str) -> None:
        self._table_name = dynamodb_table_name
        self._dynamodb = boto3.resource("dynamodb", region_name=aws_region)
        self._table = self._dynamodb.Table(dynamodb_table_name)
        # In-memory cache to avoid DynamoDB lookup on every message
        self._customer_cache: Dict[str, Optional[Dict]] = {}

    def process(
        self, message_body: str, message_attributes: Dict[str, Any]
    ) -> Optional[ValidatedRecord]:
        """Validate and parse a single SQS message.

        Args:
            message_body: Raw JSON string from SQS message body.
            message_attributes: SQS message attributes dict.

        Returns:
            ValidatedRecord if valid, None if invalid (should go to DLQ).
        """
        # Step 1: Parse JSON
        try:
            data = json.loads(message_body)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON in message: %s", exc)
            return None

        # Step 2: Check required fields
        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            logger.warning("Message missing required fields: %s", missing)
            return None

        customer_id = data["customer_id"]

        # Step 3: Verify customer exists
        customer = self._get_customer(customer_id)
        if customer is None:
            logger.warning("Unknown customer_id: %s", customer_id)
            return None

        # Step 4: Verify API key
        api_key = (
            message_attributes.get("api_key", {}).get("StringValue", "")
        )
        if not self._verify_api_key(api_key, customer.get("api_key_hash", "")):
            logger.warning("API key mismatch for customer: %s", customer_id)
            return None

        return ValidatedRecord(
            customer_id=customer_id,
            collection_timestamp=data["collection_timestamp"],
            region=data["region"],
            service=data["service"],
            resource_type=data.get("resource_type", ""),
            resource_id=data["resource_id"],
            resource_name=data.get("resource_name", ""),
            metric_name=data["metric_name"],
            metric_value=data["metric_value"],
            unit=data.get("unit", "none"),
            dimensions=data.get("dimensions", {}),
        )

    def _get_customer(self, customer_id: str) -> Optional[Dict]:
        """Fetch customer from DynamoDB with in-memory caching."""
        if customer_id in self._customer_cache:
            return self._customer_cache[customer_id]

        try:
            response = self._table.get_item(
                Key={"customer_id": customer_id, "SK": "PROFILE"}
            )
            customer = response.get("Item")
            self._customer_cache[customer_id] = customer
            return customer
        except ClientError as exc:
            logger.error("DynamoDB lookup failed for %s: %s", customer_id, exc)
            return None

    @staticmethod
    def _verify_api_key(api_key: str, stored_hash: str) -> bool:
        """Verify an API key against its stored SHA-256 hash."""
        if not api_key or not stored_hash:
            return False
        computed = hashlib.sha256(api_key.encode()).hexdigest()
        return computed == stored_hash
