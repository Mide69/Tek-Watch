"""ElastiCache cluster inventory and performance metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class ElastiCacheCollector(BaseCollector):
    """Collects ElastiCache cluster inventory and CloudWatch performance metrics."""

    SERVICE_NAME = "elasticache"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._ec = session.client("elasticache", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect ElastiCache cluster inventory and metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._ec.get_paginator("describe_cache_clusters")
            for page in paginator.paginate(ShowCacheNodeInfo=True):
                for cluster in page.get("CacheClusters", []):
                    records.extend(self._collect_cluster(cluster))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("ElastiCache collection failed in %s: %s", self.region, exc)
        return records

    def _collect_cluster(self, cluster: dict) -> List[MetricRecord]:
        """Collect all metrics for a single ElastiCache cluster."""
        records: List[MetricRecord] = []
        cluster_id = cluster.get("CacheClusterId", "")
        engine = cluster.get("Engine", "")
        engine_version = cluster.get("EngineVersion", "")
        status = cluster.get("CacheClusterStatus", "")
        node_type = cluster.get("CacheNodeType", "")
        num_nodes = cluster.get("NumCacheNodes", 0)

        base_dims = {
            "engine": engine,
            "engine_version": engine_version,
            "node_type": node_type,
            "num_nodes": num_nodes,
        }

        # Inventory record
        records.append(self._make_record(
            resource_type="cache_cluster",
            resource_id=cluster_id,
            resource_name=cluster_id,
            metric_name="cluster_status",
            metric_value=status,
            unit="none",
            dimensions=base_dims,
        ))

        if status != "available":
            return records

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        cw_metrics = [
            ("CPUUtilization",      "cpu_utilization_percent",  "percent"),
            ("FreeableMemory",      "freeable_memory_bytes",    "bytes"),
            ("CacheHits",           "cache_hits",               "count"),
            ("CacheMisses",         "cache_misses",             "count"),
            ("Evictions",           "evictions",                "count"),
            ("CurrConnections",     "current_connections",      "count"),
            ("NetworkBytesIn",      "network_bytes_in",         "bytes"),
            ("NetworkBytesOut",     "network_bytes_out",        "bytes"),
        ]

        cache_hits: Optional[float] = None
        cache_misses: Optional[float] = None

        for cw_name, metric_name, unit in cw_metrics:
            try:
                value = self._get_cw_metric(cluster_id, cw_name, start_time, end_time)
                if value is not None:
                    if metric_name == "cache_hits":
                        cache_hits = value
                    elif metric_name == "cache_misses":
                        cache_misses = value
                    records.append(self._make_record(
                        resource_type="cache_cluster",
                        resource_id=cluster_id,
                        resource_name=cluster_id,
                        metric_name=metric_name,
                        metric_value=round(value, 4),
                        unit=unit,
                        dimensions=base_dims,
                    ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.warning(
                    "CloudWatch %s failed for ElastiCache %s: %s", cw_name, cluster_id, exc
                )

        # Derived: cache hit ratio
        if cache_hits is not None and cache_misses is not None:
            total = cache_hits + cache_misses
            if total > 0:
                hit_ratio = round((cache_hits / total) * 100, 2)
                records.append(self._make_record(
                    resource_type="cache_cluster",
                    resource_id=cluster_id,
                    resource_name=cluster_id,
                    metric_name="cache_hit_ratio_percent",
                    metric_value=hit_ratio,
                    unit="percent",
                    dimensions=base_dims,
                ))

        return records

    def _get_cw_metric(
        self,
        cluster_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        """Fetch the latest CloudWatch metric value for an ElastiCache cluster."""
        response = self._cw.get_metric_statistics(
            Namespace="AWS/ElastiCache",
            MetricName=metric_name,
            Dimensions=[{"Name": "CacheClusterId", "Value": cluster_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get("Average")
