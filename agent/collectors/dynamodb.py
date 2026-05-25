"""DynamoDB table inventory and metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class DynamoDBCollector(BaseCollector):
    """Collects DynamoDB table inventory and CloudWatch capacity metrics."""

    SERVICE_NAME = "dynamodb"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._ddb = session.client("dynamodb", region_name=region)
        self._cw  = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect DynamoDB table inventory and capacity metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._ddb.get_paginator("list_tables")
            for page in paginator.paginate():
                for table_name in page.get("TableNames", []):
                    records.extend(self._collect_table(table_name))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("DynamoDB collection failed in %s: %s", self.region, exc)
        return records

    def _collect_table(self, table_name: str) -> List[MetricRecord]:
        """Collect metrics for a single DynamoDB table."""
        records: List[MetricRecord] = []
        try:
            table = self._ddb.describe_table(TableName=table_name).get("Table", {})
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("DynamoDB describe_table failed for %s: %s", table_name, exc)
            return records

        status       = table.get("TableStatus", "UNKNOWN")
        item_count   = table.get("ItemCount", 0)
        size_bytes   = table.get("TableSizeBytes", 0)
        billing_mode = table.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")

        # Provisioned throughput
        throughput   = table.get("ProvisionedThroughput", {})
        read_cap     = throughput.get("ReadCapacityUnits", 0)
        write_cap    = throughput.get("WriteCapacityUnits", 0)

        base_dims = {
            "status":       status,
            "billing_mode": billing_mode,
            "item_count":   item_count,
            "read_capacity":  read_cap,
            "write_capacity": write_cap,
        }

        records.append(self._make_record(
            resource_type="table",
            resource_id=table_name,
            resource_name=table_name,
            metric_name="table_status",
            metric_value=status,
            unit="none",
            dimensions=base_dims,
        ))

        records.append(self._make_record(
            resource_type="table",
            resource_id=table_name,
            resource_name=table_name,
            metric_name="table_size_bytes",
            metric_value=size_bytes,
            unit="bytes",
            dimensions=base_dims,
        ))

        records.append(self._make_record(
            resource_type="table",
            resource_id=table_name,
            resource_name=table_name,
            metric_name="item_count",
            metric_value=item_count,
            unit="count",
            dimensions=base_dims,
        ))

        if status != "ACTIVE":
            return records

        end_time   = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        for cw_name, metric_name, stat in [
            ("ConsumedReadCapacityUnits",  "consumed_read_capacity_units",  "Sum"),
            ("ConsumedWriteCapacityUnits", "consumed_write_capacity_units", "Sum"),
            ("ThrottledRequests",          "throttled_requests",            "Sum"),
            ("SystemErrors",               "system_errors",                 "Sum"),
            ("SuccessfulRequestLatency",   "successful_request_latency_ms", "Average"),
        ]:
            try:
                value = self._get_cw_metric(
                    table_name, cw_name, start_time, end_time, stat
                )
                if value is not None:
                    records.append(self._make_record(
                        resource_type="table",
                        resource_id=table_name,
                        resource_name=table_name,
                        metric_name=metric_name,
                        metric_value=round(value, 4),
                        unit="count" if stat == "Sum" else "milliseconds",
                        dimensions={"billing_mode": billing_mode},
                    ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.debug("CW %s failed for DDB %s: %s", cw_name, table_name, exc)

        return records

    def _get_cw_metric(
        self,
        table_name: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        stat: str = "Sum",
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace="AWS/DynamoDB",
            MetricName=metric_name,
            Dimensions=[{"Name": "TableName", "Value": table_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=[stat],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get(stat)
