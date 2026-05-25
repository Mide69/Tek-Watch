"""Lambda function inventory and invocation metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class LambdaCollector(BaseCollector):
    """Collects Lambda function inventory and CloudWatch invocation metrics."""

    SERVICE_NAME = "lambda"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._lambda = session.client("lambda", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect Lambda function inventory and 24h invocation metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._lambda.get_paginator("list_functions")
            for page in paginator.paginate():
                for fn in page.get("Functions", []):
                    records.extend(self._collect_function(fn))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("Lambda collection failed in %s: %s", self.region, exc)
        return records

    def _collect_function(self, fn: dict) -> List[MetricRecord]:
        """Collect all metrics for a single Lambda function."""
        records: List[MetricRecord] = []
        fn_name = fn.get("FunctionName", "")
        fn_arn = fn.get("FunctionArn", "")
        runtime = fn.get("Runtime", "")
        memory = fn.get("MemorySize", 128)
        timeout = fn.get("Timeout", 3)

        base_dims = {
            "runtime": runtime,
            "memory_mb": memory,
            "timeout_seconds": timeout,
        }

        # Inventory record
        records.append(self._make_record(
            resource_type="function",
            resource_id=fn_arn,
            resource_name=fn_name,
            metric_name="function_runtime",
            metric_value=runtime,
            unit="none",
            dimensions=base_dims,
        ))

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)

        # Sum metrics (24h totals)
        for cw_name, metric_name in [
            ("Invocations",         "invocations_24h"),
            ("Errors",              "errors_24h"),
            ("Throttles",           "throttles_24h"),
        ]:
            value = self._get_cw_sum(fn_name, cw_name, start_time, end_time)
            records.append(self._make_record(
                resource_type="function",
                resource_id=fn_arn,
                resource_name=fn_name,
                metric_name=metric_name,
                metric_value=value if value is not None else 0,
                unit="count",
                dimensions=base_dims,
            ))

        # Duration avg (24h)
        duration_avg = self._get_cw_stat(fn_name, "Duration", "Average", start_time, end_time)
        records.append(self._make_record(
            resource_type="function",
            resource_id=fn_arn,
            resource_name=fn_name,
            metric_name="duration_avg_ms",
            metric_value=round(duration_avg, 2) if duration_avg is not None else 0,
            unit="milliseconds",
            dimensions=base_dims,
        ))

        # ConcurrentExecutions max (24h)
        conc_max = self._get_cw_stat(fn_name, "ConcurrentExecutions", "Maximum", start_time, end_time)
        if conc_max is not None:
            records.append(self._make_record(
                resource_type="function",
                resource_id=fn_arn,
                resource_name=fn_name,
                metric_name="concurrent_executions_max",
                metric_value=int(conc_max),
                unit="count",
                dimensions=base_dims,
            ))

        return records

    def _get_cw_sum(
        self, fn_name: str, metric_name: str, start: datetime, end: datetime
    ) -> Optional[float]:
        """Get the sum of a Lambda CloudWatch metric over a time range."""
        try:
            response = self._cw.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName=metric_name,
                Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
                StartTime=start,
                EndTime=end,
                Period=86400,
                Statistics=["Sum"],
            )
            datapoints = response.get("Datapoints", [])
            return sum(d.get("Sum", 0) for d in datapoints)
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("CloudWatch %s failed for Lambda %s: %s", metric_name, fn_name, exc)
            return None

    def _get_cw_stat(
        self, fn_name: str, metric_name: str, stat: str, start: datetime, end: datetime
    ) -> Optional[float]:
        """Get a specific statistic for a Lambda CloudWatch metric."""
        try:
            response = self._cw.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName=metric_name,
                Dimensions=[{"Name": "FunctionName", "Value": fn_name}],
                StartTime=start,
                EndTime=end,
                Period=86400,
                Statistics=[stat],
            )
            datapoints = response.get("Datapoints", [])
            if not datapoints:
                return None
            return max(datapoints, key=lambda d: d["Timestamp"]).get(stat)
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("CloudWatch %s failed for Lambda %s: %s", metric_name, fn_name, exc)
            return None
