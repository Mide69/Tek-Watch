"""
Metrics writer — writes validated metric/event records to DynamoDB.

Replaces Amazon Timestream, which closed to new AWS customers on
2025-06-20 (existing Timestream customers are unaffected, but a brand new
AWS account can never create a Timestream database, in any region).

Two tables, mirroring Timestream's old metrics/events split:
  - metrics: numeric measurements (cpu_utilization_percent, mtd_blended_cost,
    etc.) — pk = "{customer_id}#{resource_id}#{metric_name}", sk = ISO8601
    time. Supports point lookups and time-range scans for one metric, plus a
    gsi_customer_time GSI (pk=customer_id, sk=time) for "everything for this
    customer in the last N hours" queries used by anomaly detection and cost
    summaries.
  - events: string-valued records (instance_state, etc.) — pk =
    "{customer_id}#{service}", sk = "{time}#{resource_id}#{metric_name}".
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from processor import ValidatedRecord

logger = logging.getLogger(__name__)

# Matches the old Timestream tables' magnetic-store retention (7 days).
_RETENTION_DAYS = 7


class MetricsWriter:
    """Writes ValidatedRecord objects to the metrics/events DynamoDB tables.

    Args:
        metrics_table_name: DynamoDB table name for numeric metric records.
        events_table_name: DynamoDB table name for event/inventory records.
        aws_region: AWS region for the DynamoDB client.
    """

    def __init__(
        self,
        metrics_table_name: str,
        events_table_name: str,
        aws_region: str,
    ) -> None:
        dynamodb = boto3.resource("dynamodb", region_name=aws_region)
        self._metrics_table = dynamodb.Table(metrics_table_name)
        self._events_table = dynamodb.Table(events_table_name)

    def write_batch(self, records: List[ValidatedRecord]) -> int:
        """Write a batch of validated records to DynamoDB.

        Args:
            records: List of ValidatedRecord objects.

        Returns:
            Number of records successfully written.
        """
        if not records:
            return 0

        # Split into numeric (metrics table) and string (events table)
        metric_records = [r for r in records if isinstance(r.metric_value, (int, float))]
        event_records = [r for r in records if not isinstance(r.metric_value, (int, float))]

        written = 0
        written += self._write_metrics(metric_records)
        written += self._write_events(event_records)
        return written

    def _write_metrics(self, records: List[ValidatedRecord]) -> int:
        if not records:
            return 0
        try:
            with self._metrics_table.batch_writer() as batch:
                for record in records:
                    batch.put_item(Item=self._to_metric_item(record))
            logger.debug("Wrote %d records to metrics table", len(records))
            return len(records)
        except ClientError as exc:
            logger.error("DynamoDB metrics write failed: %s", exc)
            return 0

    def _write_events(self, records: List[ValidatedRecord]) -> int:
        if not records:
            return 0
        try:
            with self._events_table.batch_writer() as batch:
                for record in records:
                    batch.put_item(Item=self._to_event_item(record))
            logger.debug("Wrote %d records to events table", len(records))
            return len(records)
        except ClientError as exc:
            logger.error("DynamoDB events write failed: %s", exc)
            return 0

    def _to_metric_item(self, record: ValidatedRecord) -> Dict[str, Any]:
        dt = self._parse_timestamp(record.collection_timestamp)
        time_iso = dt.isoformat()
        resource_id = record.resource_id[:256]

        item: Dict[str, Any] = {
            "pk": f"{record.customer_id}#{resource_id}#{record.metric_name}",
            "time": time_iso,
            "customer_id": record.customer_id,
            "service": record.service,
            "resource_id": resource_id,
            "resource_name": record.resource_name or "",
            "resource_type": record.resource_type or "unknown",
            "metric_name": record.metric_name[:256],
            "value": Decimal(str(record.metric_value)),
            "region": record.region,
            "unit": record.unit,
            "expires_at": self._expires_at(dt),
        }
        if record.dimensions:
            # Mirrors Timestream's 128-dimension / 60-char-name / 256-char-value caps
            item["dimensions"] = {
                str(k)[:60]: str(v)[:256] for k, v in list(record.dimensions.items())[:128]
            }
        return item

    def _to_event_item(self, record: ValidatedRecord) -> Dict[str, Any]:
        dt = self._parse_timestamp(record.collection_timestamp)
        time_iso = dt.isoformat()
        resource_id = record.resource_id[:256]

        return {
            "pk": f"{record.customer_id}#{record.service}",
            "sk": f"{time_iso}#{resource_id}#{record.metric_name}",
            "time": time_iso,
            "customer_id": record.customer_id,
            "service": record.service,
            "resource_id": resource_id,
            "resource_name": record.resource_name or "",
            "metric_name": record.metric_name[:256],
            "value": str(record.metric_value)[:2048],
            "expires_at": self._expires_at(dt),
        }

    @staticmethod
    def _parse_timestamp(collection_timestamp: str) -> datetime:
        try:
            return datetime.fromisoformat(collection_timestamp.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _expires_at(dt: datetime) -> int:
        return int((dt + timedelta(days=_RETENTION_DAYS)).timestamp())
