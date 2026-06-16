"""
Timestream writer — writes validated metric records to Amazon Timestream.

Uses batch writes (max 100 records per call) for efficiency.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

from processor import ValidatedRecord

logger = logging.getLogger(__name__)

_TIMESTREAM_BATCH_SIZE = 100


class TimestreamWriter:
    """Writes ValidatedRecord objects to Amazon Timestream.

    Args:
        database_name: Timestream database name.
        metrics_table: Table name for numeric metric records.
        events_table: Table name for event/inventory records.
        aws_region: AWS region for Timestream client.
    """

    def __init__(
        self,
        database_name: str,
        metrics_table: str,
        events_table: str,
        aws_region: str,
    ) -> None:
        self._database = database_name
        self._metrics_table = metrics_table
        self._events_table = events_table
        self._ts = boto3.client("timestream-write", region_name=aws_region)

    def write_batch(self, records: List[ValidatedRecord]) -> int:
        """Write a batch of validated records to Timestream.

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
        written += self._write_to_table(metric_records, self._metrics_table, "DOUBLE")
        written += self._write_to_table(event_records, self._events_table, "VARCHAR")
        return written

    def _write_to_table(
        self, records: List[ValidatedRecord], table_name: str, measure_type: str
    ) -> int:
        """Write records to a specific Timestream table in batches."""
        if not records:
            return 0

        written = 0
        for i in range(0, len(records), _TIMESTREAM_BATCH_SIZE):
            batch = records[i:i + _TIMESTREAM_BATCH_SIZE]
            ts_records = [
                self._to_timestream_record(r, measure_type) for r in batch
            ]

            try:
                self._ts.write_records(
                    DatabaseName=self._database,
                    TableName=table_name,
                    Records=ts_records,
                    CommonAttributes={},
                )
                written += len(batch)
                logger.debug(
                    "Wrote %d records to %s/%s", len(batch), self._database, table_name
                )
            except self._ts.exceptions.RejectedRecordsException as exc:
                rejected = exc.response.get("RejectedRecords", [])
                logger.warning(
                    "Timestream rejected %d records: %s", len(rejected), rejected
                )
                written += len(batch) - len(rejected)
            except ClientError as exc:
                logger.error(
                    "Timestream write failed for table %s: %s", table_name, exc
                )

        return written

    def _to_timestream_record(
        self, record: ValidatedRecord, measure_type: str
    ) -> Dict[str, Any]:
        """Convert a ValidatedRecord to a Timestream write_records entry."""
        # Parse timestamp to milliseconds epoch
        try:
            dt = datetime.fromisoformat(
                record.collection_timestamp.replace("Z", "+00:00")
            )
        except ValueError:
            dt = datetime.now(timezone.utc)

        time_ms = str(int(dt.timestamp() * 1000))

        # Build dimensions
        dimensions = [
            {"Name": "customer_id", "Value": record.customer_id},
            {"Name": "region",      "Value": record.region},
            {"Name": "service",     "Value": record.service},
            {"Name": "resource_type", "Value": record.resource_type or "unknown"},
            {"Name": "resource_id", "Value": record.resource_id[:256]},
            {"Name": "metric_name", "Value": record.metric_name},
        ]

        # Add extra dimensions (max 128 chars per value)
        for k, v in (record.dimensions or {}).items():
            if len(dimensions) >= 128:
                break
            dimensions.append({"Name": str(k)[:60], "Value": str(v)[:256]})

        # Measure value
        if measure_type == "DOUBLE":
            measure_value = str(float(record.metric_value))
        else:
            measure_value = str(record.metric_value)[:2048]

        return {
            "Dimensions": dimensions,
            "MeasureName": record.metric_name[:256],
            "MeasureValue": measure_value,
            "MeasureValueType": measure_type,
            "Time": time_ms,
            "TimeUnit": "MILLISECONDS",
        }
