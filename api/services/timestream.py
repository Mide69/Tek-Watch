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
import math
import re
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from config import load_config

logger = logging.getLogger(__name__)

_SAFE_ID_RE    = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')
_SAFE_RANGE_RE = re.compile(r'^(24h|7d|30d|90d|5m|1h)$')

# How far back "what exists right now" looks.
#
# This must be comfortably wider than the agent's collection interval, which
# the CloudFormation template defaults to rate(5 minutes). The overview used a
# 5m window — exactly the interval — so the newest reading was always between
# 0 and 5 minutes old *plus* however long the agent took to scan every region,
# reach SQS and be drained by the consumer. Whenever that sum crossed five
# minutes the window held nothing and the dashboard read zero, then filled in
# again on the next cycle. An estate does not blink in and out of existence,
# so the window should not be tight enough to make it look like it does.
_INVENTORY_WINDOW = "1h"

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
        """Get 7-day averages and std devs for anomaly detection.

        Computed while the pages stream in (Welford's method), keeping four
        numbers per metric rather than every row. A week at one sample every
        five minutes is about 2,000 rows per metric; holding them all as
        Python dicts for a whole account, in each of the API's two workers,
        outgrew the 512 MB task and took the API down on deploy.
        """
        cid = _safe(customer_id)
        # key -> [count, mean, sum of squared deviations, earliest time]
        stats: Dict[tuple, List[Any]] = {}
        try:
            for r in self._iter_query(
                self._metrics_table,
                Key("customer_id").eq(cid) & Key("time").gte(self._since_iso("7d")),
                index_name="gsi_customer_time",
                scan_forward=True,
            ):
                try:
                    value = float(r["value"])
                except (KeyError, TypeError, ValueError):
                    continue
                key = (r.get("service"), r.get("resource_id"), r.get("metric_name"))
                entry = stats.get(key)
                if entry is None:
                    entry = stats[key] = [0, 0.0, 0.0, ""]
                entry[0] += 1
                delta = value - entry[1]
                entry[1] += delta / entry[0]
                entry[2] += delta * (value - entry[1])
                t = str(r.get("time") or "")
                if t and (not entry[3] or t < entry[3]):
                    entry[3] = t
        except ClientError as exc:
            # A baseline built from part of the week would make ordinary
            # readings look anomalous. No baseline at all is the safe answer.
            logger.error("DynamoDB GSI query failed: %s", exc)
            return []

        # samples and first_time let the detector refuse to judge a metric it
        # has barely seen: a resource created an hour ago has no "normal" yet.
        return [
            {
                "service": service,
                "resource_id": resource_id,
                "metric_name": metric_name,
                "avg_value": mean,
                "stddev_value": math.sqrt(m2 / (n - 1)) if n > 1 else 0.0,
                "samples": n,
                "first_time": first_time or None,
            }
            for (service, resource_id, metric_name), (n, mean, m2, first_time) in stats.items()
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

        # One row per calendar day, not one per collection.
        #
        # daily_blended_cost is a running total for the day, and the agent
        # re-reports it every cycle. Returning every row made the chart draw a
        # point per collection instead of per day, and the caller sums this
        # list for the month-to-date figure — so a single day at rate(5
        # minutes) was added 288 times. The cost page overstated spend by
        # roughly the collection frequency, growing worse the longer the agent
        # ran. Keeping the last reading for each day gives the day's total once.
        by_day: Dict[str, Dict[str, Any]] = {}
        for r in sorted(filtered, key=lambda r: str(r.get("time", ""))):
            day = str(r.get("time", ""))[:10]
            if day:
                by_day[day] = r
        return [
            {"time": r["time"], "cost": float(r["value"])}
            for _, r in sorted(by_day.items())
        ]

    def get_service_costs(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get month-to-date cost breakdown by AWS service."""
        cid = _safe(customer_id)
        rows = self._query_metrics_by_customer(cid, self._since_iso("24h"))
        filtered = [
            r for r in rows
            if r.get("service") == "cost_explorer" and r.get("metric_name") == "mtd_blended_cost"
        ]
        # Latest reading per service. Same duplication as the daily costs:
        # every collection re-reports month-to-date for each service, so the
        # breakdown table listed each service once per cycle.
        latest: Dict[str, Dict[str, Any]] = {}
        for r in sorted(filtered, key=lambda r: str(r.get("time", ""))):
            name = r.get("resource_name") or r.get("resource_id") or "unknown"
            latest[str(name)] = r

        result = [
            {"aws_service": name, "mtd_cost": float(r["value"])}
            for name, r in latest.items()
        ]
        result.sort(key=lambda r: r["mtd_cost"], reverse=True)
        return result

    # ── Inventory ─────────────────────────────────────────────────────────────
    #
    # Everything above answers "what were the numbers for this metric". The
    # dashboard's resource pages ask a different question — "what do I have" —
    # and nothing answered it. Each page was handed the raw rows and expected
    # to find an object per resource, so the storage page read b.object_count
    # on a row that only ever carries metric_name and value, and the whole page
    # died on `Cannot read properties of undefined`.
    #
    # A resource is not a row. It is every row about the same resource_id
    # folded together: the newest value of each metric, plus the descriptive
    # dimensions the collector went and fetched. That fold is what these two
    # methods do, once, so every router can stop reinventing it.

    def _fold_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Fold metric rows into one entry per resource, newest value wins."""
        resources: Dict[str, Dict[str, Any]] = {}

        for row in sorted(rows, key=lambda r: str(r.get("time", ""))):
            rid = row.get("resource_id")
            if not rid:
                continue

            entry = resources.setdefault(
                str(rid),
                {
                    "resource_id": str(rid),
                    "resource_name": "",
                    "resource_type": "",
                    "region": "",
                    "service": "",
                    "last_seen": "",
                    "metrics": {},
                },
            )

            for field in ("resource_name", "resource_type", "region", "service"):
                value = row.get(field)
                if value:
                    entry[field] = value

            time = row.get("time")
            if time and str(time) > str(entry["last_seen"]):
                entry["last_seen"] = str(time)

            metric = row.get("metric_name")
            if metric:
                value = row.get("value")
                # Metric rows store Decimal, event rows store the raw string.
                # Callers want a number wherever the value is one, so that a
                # template can format it without knowing which table it lived in.
                try:
                    entry["metrics"][str(metric)] = float(value)
                except (TypeError, ValueError):
                    entry["metrics"][str(metric)] = value

            dimensions = row.get("dimensions")
            if isinstance(dimensions, dict):
                entry.setdefault("dimensions", {}).update(
                    {str(k): v for k, v in dimensions.items()}
                )

        for entry in resources.values():
            entry.setdefault("dimensions", {})
            if not entry["resource_name"]:
                entry["resource_name"] = entry["resource_id"]

        return resources

    def get_service_inventory(
        self, customer_id: str, service: str, time_range: str = _INVENTORY_WINDOW
    ) -> List[Dict[str, Any]]:
        """Every resource of one service, with its latest metrics and dimensions.

        Reads both tables. The split between them is a storage detail — a
        bucket's state is a string and lives in events while its size is a
        number and lives in metrics — and a customer looking at their buckets
        should not be able to tell. Reading only events, as the routers did,
        meant the numbers were never in the response at all.
        """
        cid = _safe(customer_id)
        svc = _safe(service)
        _safe(time_range, _SAFE_RANGE_RE)
        since = self._since_iso(time_range)

        rows: List[Dict[str, Any]] = []
        try:
            rows.extend(
                self._paginated_query(
                    self._events_table,
                    Key("pk").eq(f"{cid}#{svc}") & Key("sk").gte(since),
                    scan_forward=True,
                )
            )
        except ClientError as exc:
            logger.error("DynamoDB events query failed: %s", exc)

        rows.extend(
            r for r in self._query_metrics_by_customer(cid, since)
            if r.get("service") == svc
        )

        inventory = list(self._fold_rows(rows).values())
        inventory.sort(key=lambda r: str(r.get("resource_name") or ""))
        return inventory

    def get_resource_inventory(
        self, customer_id: str, time_range: str = _INVENTORY_WINDOW
    ) -> Dict[str, Any]:
        """Total distinct resources, broken down by region and by service.

        The overview counted EC2 only, over a five-minute window. An account
        with no EC2 instances — this platform's first real customer is one —
        therefore reported zero resources while the agent was reporting fifty
        across eighteen regions, and the region panel beside it was hardcoded.
        """
        cid = _safe(customer_id)
        _safe(time_range, _SAFE_RANGE_RE)
        since = self._since_iso(time_range)

        rows = self._query_metrics_by_customer(cid, since)

        by_region: Dict[str, set] = {}
        by_service: Dict[str, set] = {}
        seen: set = set()

        for row in rows:
            service = str(row.get("service") or "unknown")
            rid = row.get("resource_id")
            if not rid:
                continue
            # A resource_id is only unique within its service: the cost
            # collector reports the customer id as a resource, and so would
            # anything else keyed on the account.
            key = (service, str(rid))
            seen.add(key)
            by_region.setdefault(str(row.get("region") or "unknown"), set()).add(key)
            by_service.setdefault(service, set()).add(key)

        return {
            "total": len(seen),
            "by_region": sorted(
                ({"region": r, "count": len(v)} for r, v in by_region.items()),
                key=lambda x: (-x["count"], x["region"]),
            ),
            "by_service": sorted(
                ({"service": s, "count": len(v)} for s, v in by_service.items()),
                key=lambda x: (-x["count"], x["service"]),
            ),
        }

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
    def _iter_query(
        table,
        key_condition,
        index_name: Optional[str] = None,
        scan_forward: bool = True,
    ) -> Iterator[Dict[str, Any]]:
        """Every item a query matches, one page in memory at a time."""
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_forward,
        }
        if index_name:
            kwargs["IndexName"] = index_name

        while True:
            resp = table.query(**kwargs)
            yield from resp.get("Items", [])
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key

    @staticmethod
    def _paginated_query(
        table,
        key_condition,
        index_name: Optional[str] = None,
        scan_forward: bool = True,
    ) -> List[Dict[str, Any]]:
        return list(TimestreamQueryService._iter_query(table, key_condition, index_name, scan_forward))

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
