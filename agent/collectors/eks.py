"""EKS cluster inventory and metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class EKSCollector(BaseCollector):
    """Collects EKS cluster inventory and CloudWatch Container Insights metrics."""

    SERVICE_NAME = "eks"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._eks = session.client("eks", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect EKS cluster inventory and node group metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._eks.get_paginator("list_clusters")
            for page in paginator.paginate():
                for cluster_name in page.get("clusters", []):
                    records.extend(self._collect_cluster(cluster_name))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("EKS collection failed in %s: %s", self.region, exc)
        return records

    def _collect_cluster(self, cluster_name: str) -> List[MetricRecord]:
        """Collect metrics for a single EKS cluster."""
        records: List[MetricRecord] = []
        try:
            response = self._eks.describe_cluster(name=cluster_name)
            cluster = response.get("cluster", {})

            status = cluster.get("status", "unknown")
            version = cluster.get("version", "")
            endpoint = cluster.get("endpoint", "")
            role_arn = cluster.get("roleArn", "")

            base_dims = {
                "version": version,
                "status": status,
            }

            records.append(self._make_record(
                resource_type="cluster",
                resource_id=cluster_name,
                resource_name=cluster_name,
                metric_name="cluster_status",
                metric_value=status,
                unit="none",
                dimensions=base_dims,
            ))

            if status != "ACTIVE":
                return records

            # Collect node groups
            records.extend(self._collect_node_groups(cluster_name))

            # CloudWatch Container Insights metrics (if enabled)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=10)

            for cw_name, metric_name, unit, stat in [
                ("node_cpu_utilization",    "node_cpu_utilization_percent",    "percent", "Average"),
                ("node_memory_utilization", "node_memory_utilization_percent", "percent", "Average"),
                ("node_network_total_bytes","node_network_total_bytes",        "bytes",   "Sum"),
                ("pod_cpu_utilization",     "pod_cpu_utilization_percent",     "percent", "Average"),
                ("pod_memory_utilization",  "pod_memory_utilization_percent",  "percent", "Average"),
            ]:
                try:
                    value = self._get_cw_metric(
                        cluster_name, cw_name, start_time, end_time, stat
                    )
                    if value is not None:
                        records.append(self._make_record(
                            resource_type="cluster",
                            resource_id=cluster_name,
                            resource_name=cluster_name,
                            metric_name=metric_name,
                            metric_value=round(value, 4),
                            unit=unit,
                            dimensions=base_dims,
                        ))
                except (ClientError, EndpointResolutionError) as exc:
                    logger.debug("CW %s failed for EKS %s: %s", cw_name, cluster_name, exc)

        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("EKS describe_cluster failed for %s: %s", cluster_name, exc)
        return records

    def _collect_node_groups(self, cluster_name: str) -> List[MetricRecord]:
        """Collect EKS managed node group inventory."""
        records: List[MetricRecord] = []
        try:
            paginator = self._eks.get_paginator("list_nodegroups")
            for page in paginator.paginate(clusterName=cluster_name):
                for ng_name in page.get("nodegroups", []):
                    try:
                        ng_response = self._eks.describe_nodegroup(
                            clusterName=cluster_name, nodegroupName=ng_name
                        )
                        ng = ng_response.get("nodegroup", {})
                        status = ng.get("status", "unknown")
                        instance_types = ",".join(ng.get("instanceTypes", []))
                        scaling = ng.get("scalingConfig", {})
                        desired = scaling.get("desiredSize", 0)
                        min_size = scaling.get("minSize", 0)
                        max_size = scaling.get("maxSize", 0)

                        records.append(self._make_record(
                            resource_type="node_group",
                            resource_id=f"{cluster_name}/{ng_name}",
                            resource_name=ng_name,
                            metric_name="node_group_status",
                            metric_value=status,
                            unit="none",
                            dimensions={
                                "cluster": cluster_name,
                                "instance_types": instance_types,
                                "desired_size": desired,
                                "min_size": min_size,
                                "max_size": max_size,
                            },
                        ))
                        records.append(self._make_record(
                            resource_type="node_group",
                            resource_id=f"{cluster_name}/{ng_name}",
                            resource_name=ng_name,
                            metric_name="desired_node_count",
                            metric_value=desired,
                            unit="count",
                            dimensions={"cluster": cluster_name},
                        ))
                    except (ClientError, EndpointResolutionError) as exc:
                        logger.warning("EKS node group %s failed: %s", ng_name, exc)
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("EKS list_nodegroups failed for %s: %s", cluster_name, exc)
        return records

    def _get_cw_metric(
        self,
        cluster_name: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        stat: str = "Average",
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace="ContainerInsights",
            MetricName=metric_name,
            Dimensions=[{"Name": "ClusterName", "Value": cluster_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=[stat],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get(stat)
