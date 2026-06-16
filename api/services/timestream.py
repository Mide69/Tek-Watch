"""Metrics query service — all metric queries go through here.

Originally backed by Amazon Timestream. Rewritten against DynamoDB after
Timestream for LiveAnalytics closed to new AWS customers on 2025-06-20 — a
new AWS account can never create a Timestream database, in any region
(existing Timestream customers are unaffected, but that doesn't help here).

Class name and every public method signature/return shape are kept
unchanged so the ~16 call sites across routers/, chat_service.py, and
alerting/ don't need to change at all — only the storage backend changed.
DynamoDB's query API is parameterized (boto3's Key() condition builder), so
the injection-prevention _safe() validation below is now defense-in-depth
rather than strictly required, but kept anyway: it preserves the original
input-validation behavior (raises ValueError on malformed IDs) and costs
nothing.
"""
import logging
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)

_SAFE_ID_RE    = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')
_SAFE_RANGE_RE = re.compile(r'^(24h|7d|30d|90d|5m|1h)$')

_RANGE_TO_TIMEDELTA = {
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}


def _safe(value: str, pattern: re.Pattern = _SAFE_ID_RE) -> str:
    """Raise ValueError if value contains characters outside the allowlist."""
    if not pattern.match(value):
        raise ValueError(f"Unsafe value rejected: {value!r}")
    return value


class TimestreamQueryService:
    """Executes metric queries scoped to a customer_id, against DynamoDB.

    All queries enforce customer_id isolation — the customer_id is
    always injected from the verified JWT, never from caller input.
    """

    def __init__(self) -> None:
        config = load_config()
        dynamodb = boto3.resource("dynamodb", region_name=config.aws_region)
        self._metrics_table = dynamodb.Table(config.dynamodb_metrics_table)
        self._events_table = dynamodb.Table(config.dynamodb_events_table)

    # ── Overview ──────────────────────────────────────────────────────────────

    def get_latest_metric(
        self, customer_id: str, service: str, resource_id: str, metric_name: str
    ) -> Optional[float]:
        """Get the most recent value for a specific metric."""
        cid = _safe(customer_id)
        _safe(service)
        rid = _safe(resource_id)
        met = _safe(metric_name)
        pk = f"{cid}#{rid}#{met}"

        try:
            resp = self._metrics_table.query(
                KeyConditionExpression=Key("pk").eq(pk),
                ScanIndexForward=False,
                Limit=1,
            )
        except ClientError as exc:
            logger.error("DynamoDB query failed: %s", exc)
            return None

        items = resp.get("Items", [])
        if items and items[0].get("value") is not None:
            return float(items[0]["value"])
        return None

    def get_time_series(
        self,
        customer_id: str,
        resource_id: str,
        metric_name: str,
        time_range: str = "24h",
    ) -> List[Dict[str, Any]]:
        """Get time-series data for a resource metric."""
        cid = _safe(customer_id)
        rid = _safe(resource_id)
        met = _safe(metric_name)
        _safe(time_range, _SAFE_RANGE_RE)

        pk = f"{cid}#{rid}#{met}"
        since = self._since_iso(time_range)
        rows = self._query_metrics_by_pk(pk, since)

        bin_size = self._get_bin_size(time_range)
        if bin_size is None:
            return [{"time": r["time"], "value": float(r["value"])} for r in rows]
        return self._bin_average(rows, bin_size)

    def get_resources_by_service(
        self, customer_id: str, service: str, time_range: str = "5m"
    ) -> List[Dict[str, Any]]:
        """Get all resources of a service type with their latest metrics."""
        cid = _safe(customer_id)
        svc = _safe(service)
        _safe(time_range, _SAFE_RANGE_RE)

        pk = f"{cid}#{svc}"
        since = self._since_iso(time_range)

        try:
            rows = self._paginated_query(
                self._events_table,
                Key("pk").eq(pk) & Key("sk").gte(since),
                scan_forward=False,
            )
        except ClientError as exc:
            logger.error("DynamoDB query failed: %s", exc)
            return []

        return [
            {
                "resource_id": r.get("resource_id"),
                "resource_name": r.get("resource_name"),
                "metric_name": r.get("metric_name"),
                "value": r.get("value"),
                "time": r.get("time"),
            }
            for r in rows
        ]

    def get_7day_summary(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get 7-day averages and std devs for anomaly detection."""
        cid = _safe(customer_id)
        rows = self._query_metrics_by_customer(cid, self._since_iso("7d"))

        groups: Dict[tuple, List[float]] = {}
        for r in rows:
            key = (r.get("service"), r.get("resource_id"), r.get("metric_name"))
            groups.setdefault(key, []).append(float(r["value"]))

        return [
            {
                "service": service,
                "resource_id": resource_id,
                "metric_name": metric_name,
                "avg_value": statistics.mean(values),
                "stddev_value": statistics.stdev(values) if len(values) > 1 else 0.0,
            }
            for (service, resource_id, metric_name), values in groups.items()
        ]

    def get_last_hour(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all metric values from the last hour for anomaly detection."""
        cid = _safe(customer_id)
        rows = self._query_metrics_by_customer(cid, self._since_iso("1h"))
        return [
            {
                "service": r.get("service"),
                "resource_id": r.get("resource_id"),
                "metric_name": r.get("metric_name"),
                "value": float(r["value"]),
                "time": r.get("time"),
            }
            for r in rows
        ]

    def get_daily_costs(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get daily cost records for the last 30 days."""
        cid = _safe(customer_id)
        rows = self._query_metrics_by_customer(cid, self._since_iso("30d"))
        filtered = [
            r for r in rows
            if r.get("service") == "cost_explorer" and r.get("metric_name") == "daily_blended_cost"
        ]
        return [{"time": r["time"], "cost": float(r["value"])} for r in filtered]

    def get_service_costs(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get month-to-date cost breakdown by AWS service."""
        cid = _safe(customer_id)
        rows = self._query_metrics_by_customer(cid, self._since_iso("24h"))
        filtered = [
            r for r in rows
            if r.get("service") == "cost_explorer" and r.get("metric_name") == "mtd_blended_cost"
        ]
        result = [
            {"aws_service": r.get("resource_name"), "mtd_cost": float(r["value"])}
            for r in filtered
        ]
        result.sort(key=lambda r: r["mtd_cost"], reverse=True)
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _since_iso(time_range: str) -> str:
        delta = _RANGE_TO_TIMEDELTA.get(time_range, _RANGE_TO_TIMEDELTA["24h"])
        return (datetime.now(timezone.utc) - delta).isoformat()

    def _query_metrics_by_pk(self, pk: str, since_iso: str) -> List[Dict[str, Any]]:
        try:
            return self._paginated_query(
                self._metrics_table,
                Key("pk").eq(pk) & Key("time").gte(since_iso),
                scan_forward=True,
            )
        except ClientError as exc:
            logger.error("DynamoDB query failed: %s", exc)
            return []

    def _query_metrics_by_customer(self, customer_id: str, since_iso: str) -> List[Dict[str, Any]]:
        try:
            return self._paginated_query(
                self._metrics_table,
                Key("customer_id").eq(customer_id) & Key("time").gte(since_iso),
                index_name="gsi_customer_time",
                scan_forward=True,
            )
        except ClientError as exc:
            logger.error("DynamoDB GSI query failed: %s", exc)
            return []

    @staticmethod
    def _paginated_query(
        table,
        key_condition,
        index_name: Optional[str] = None,
        scan_forward: bool = True,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_forward,
        }
        if index_name:
            kwargs["IndexName"] = index_name

        while True:
            resp = table.query(**kwargs)
            items.extend(resp.get("Items", []))
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
        return items

    @staticmethod
    def _get_bin_size(time_range: str) -> Optional[timedelta]:
        """Return downsampling bin size, or None for raw (unbinned) data."""
        if time_range == "30d":
            return timedelta(hours=1)
        if time_range == "90d":
            return timedelta(hours=6)
        return None

    @staticmethod
    def _bin_average(rows: List[Dict[str, Any]], bin_size: timedelta) -> List[Dict[str, Any]]:
        """Downsample raw rows into bin_size buckets, averaging values per bucket.

        DynamoDB has no server-side aggregation (unlike Timestream's bin()),
        so this happens in Python after fetching the raw rows for the range.
        """
        if not rows:
            return []
        bin_seconds = bin_size.total_seconds()
        buckets: Dict[float, List[float]] = {}
        for r in rows:
            try:
                dt = datetime.fromisoformat(r["time"])
            except (ValueError, KeyError):
                continue
            bucket_epoch = (dt.timestamp() // bin_seconds) * bin_seconds
            buckets.setdefault(bucket_epoch, []).append(float(r["value"]))

        return [
            {
                "time": datetime.fromtimestamp(bucket_epoch, tz=timezone.utc).isoformat(),
                "value": statistics.mean(buckets[bucket_epoch]),
            }
            for bucket_epoch in sorted(buckets)
        ]
