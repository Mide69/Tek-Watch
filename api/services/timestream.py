"""Timestream query service — all metric queries go through here."""
import logging
import re
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)

# Allowlist pattern for values interpolated into Timestream queries.
# customer_id is always TT-XXXX; service/metric names are alphanumeric + underscore.
_SAFE_ID_RE    = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')
_SAFE_RANGE_RE = re.compile(r'^(24h|7d|30d|90d|5m|1h)$')


def _safe(value: str, pattern: re.Pattern = _SAFE_ID_RE) -> str:
    """Raise ValueError if value contains characters outside the allowlist."""
    if not pattern.match(value):
        raise ValueError(f"Unsafe value rejected for Timestream query: {value!r}")
    return value


class TimestreamQueryService:
    """Executes Timestream queries scoped to a customer_id.

    All queries enforce customer_id isolation — the customer_id is
    always injected from the verified JWT, never from caller input.
    """

    def __init__(self) -> None:
        config = load_config()
        self._client = boto3.client("timestream-query", region_name=config.aws_region)
        self._database = config.timestream_database_name
        self._metrics_table = config.timestream_metrics_table
        self._events_table = config.timestream_events_table

    def _run_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a Timestream query and return rows as list of dicts."""
        rows: List[Dict[str, Any]] = []
        try:
            paginator = self._client.get_paginator("query")
            for page in paginator.paginate(QueryString=query):
                column_info = page.get("ColumnInfo", [])
                for row in page.get("Rows", []):
                    data = row.get("Data", [])
                    record: Dict[str, Any] = {}
                    for i, col in enumerate(column_info):
                        col_name = col.get("Name", f"col_{i}")
                        cell = data[i] if i < len(data) else {}
                        record[col_name] = (
                            cell.get("ScalarValue")
                            or cell.get("NullValue")
                        )
                    rows.append(record)
        except ClientError as exc:
            logger.error("Timestream query failed: %s | query: %s", exc, query[:200])
        return rows

    # ── Overview ──────────────────────────────────────────────────────────────

    def get_latest_metric(
        self, customer_id: str, service: str, resource_id: str, metric_name: str
    ) -> Optional[float]:
        """Get the most recent value for a specific metric."""
        cid = _safe(customer_id)
        svc = _safe(service)
        rid = _safe(resource_id)
        met = _safe(metric_name)
        query = f"""
            SELECT measure_value::double AS value
            FROM "{self._database}"."{self._metrics_table}"
            WHERE customer_id = '{cid}'
              AND service = '{svc}'
              AND resource_id = '{rid}'
              AND metric_name = '{met}'
            ORDER BY time DESC
            LIMIT 1
        """
        rows = self._run_query(query)
        if rows and rows[0].get("value") is not None:
            return float(rows[0]["value"])
        return None

    def get_time_series(
        self,
        customer_id: str,
        resource_id: str,
        metric_name: str,
        time_range: str = "24h",
    ) -> List[Dict[str, Any]]:
        """Get time-series data for a resource metric."""
        cid      = _safe(customer_id)
        rid      = _safe(resource_id)
        met      = _safe(metric_name)
        ago_expr = _safe(time_range, _SAFE_RANGE_RE)
        bin_size = self._get_bin_size(time_range)

        if bin_size:
            query = f"""
                SELECT bin(time, {bin_size}) AS time,
                       AVG(measure_value::double) AS value
                FROM "{self._database}"."{self._metrics_table}"
                WHERE customer_id = '{cid}'
                  AND resource_id = '{rid}'
                  AND metric_name = '{met}'
                  AND time >= ago({ago_expr})
                GROUP BY bin(time, {bin_size})
                ORDER BY time ASC
            """
        else:
            query = f"""
                SELECT time, measure_value::double AS value
                FROM "{self._database}"."{self._metrics_table}"
                WHERE customer_id = '{cid}'
                  AND resource_id = '{rid}'
                  AND metric_name = '{met}'
                  AND time >= ago({ago_expr})
                ORDER BY time ASC
            """
        return self._run_query(query)

    def get_resources_by_service(
        self, customer_id: str, service: str, time_range: str = "5m"
    ) -> List[Dict[str, Any]]:
        """Get all resources of a service type with their latest metrics."""
        cid      = _safe(customer_id)
        svc      = _safe(service)
        ago_expr = _safe(time_range, _SAFE_RANGE_RE)
        query = f"""
            SELECT resource_id, resource_name, metric_name,
                   measure_value::varchar AS value, time
            FROM "{self._database}"."{self._events_table}"
            WHERE customer_id = '{cid}'
              AND service = '{svc}'
              AND time >= ago({ago_expr})
            ORDER BY time DESC
        """
        return self._run_query(query)

    def get_7day_summary(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get 7-day averages and std devs for anomaly detection."""
        cid = _safe(customer_id)
        query = f"""
            SELECT service, resource_id, metric_name,
                   AVG(measure_value::double) AS avg_value,
                   STDDEV(measure_value::double) AS stddev_value
            FROM "{self._database}"."{self._metrics_table}"
            WHERE customer_id = '{cid}'
              AND time >= ago(7d)
            GROUP BY service, resource_id, metric_name
        """
        return self._run_query(query)

    def get_last_hour(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all metric values from the last hour for anomaly detection."""
        cid = _safe(customer_id)
        query = f"""
            SELECT service, resource_id, metric_name,
                   measure_value::double AS value, time
            FROM "{self._database}"."{self._metrics_table}"
            WHERE customer_id = '{cid}'
              AND time >= ago(1h)
            ORDER BY time ASC
        """
        return self._run_query(query)

    def get_daily_costs(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get daily cost records for the last 30 days."""
        cid = _safe(customer_id)
        query = f"""
            SELECT time, measure_value::double AS cost
            FROM "{self._database}"."{self._metrics_table}"
            WHERE customer_id = '{cid}'
              AND service = 'cost_explorer'
              AND metric_name = 'daily_blended_cost'
              AND time >= ago(30d)
            ORDER BY time ASC
        """
        return self._run_query(query)

    def get_service_costs(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get month-to-date cost breakdown by AWS service."""
        cid = _safe(customer_id)
        query = f"""
            SELECT resource_name AS aws_service,
                   measure_value::double AS mtd_cost
            FROM "{self._database}"."{self._metrics_table}"
            WHERE customer_id = '{cid}'
              AND service = 'cost_explorer'
              AND metric_name = 'mtd_blended_cost'
              AND time >= ago(24h)
            ORDER BY mtd_cost DESC
        """
        return self._run_query(query)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _range_to_ago(time_range: str) -> str:
        mapping = {"24h": "24h", "7d": "7d", "30d": "30d", "90d": "90d", "5m": "5m", "1h": "1h"}
        return mapping.get(time_range, "24h")

    @staticmethod
    def _get_bin_size(time_range: str) -> Optional[str]:
        """Return Timestream bin() size for downsampling, or None for raw."""
        if time_range == "30d":
            return "1h"
        if time_range == "90d":
            return "6h"
        return None
