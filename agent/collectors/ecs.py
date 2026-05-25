"""ECS cluster and service inventory and performance metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class ECSCollector(BaseCollector):
    """Collects ECS cluster and service inventory and CloudWatch metrics."""

    SERVICE_NAME = "ecs"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._ecs = session.client("ecs", region_name=region)
        self._cw  = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect ECS cluster and service inventory and metrics."""
        records: List[MetricRecord] = []
        try:
            cluster_arns = self._ecs.list_clusters().get("clusterArns", [])
            if not cluster_arns:
                return records

            clusters_resp = self._ecs.describe_clusters(clusters=cluster_arns)
            for cluster in clusters_resp.get("clusters", []):
                records.extend(self._collect_cluster(cluster))

        except (ClientError, EndpointResolutionError) as exc:
            logger.error("ECS collection failed in %s: %s", self.region, exc)
        return records

    def _collect_cluster(self, cluster: dict) -> List[MetricRecord]:
        """Collect metrics for a single ECS cluster."""
        records: List[MetricRecord] = []
        cluster_arn  = cluster.get("clusterArn", "")
        cluster_name = cluster.get("clusterName", cluster_arn.split("/")[-1])
        status       = cluster.get("status", "UNKNOWN")

        records.append(self._make_record(
            resource_type="cluster",
            resource_id=cluster_name,
            resource_name=cluster_name,
            metric_name="cluster_status",
            metric_value=status,
            unit="none",
            dimensions={
                "running_tasks":   cluster.get("runningTasksCount", 0),
                "pending_tasks":   cluster.get("pendingTasksCount", 0),
                "active_services": cluster.get("activeServicesCount", 0),
            },
        ))

        if status != "ACTIVE":
            return records

        # Collect services
        try:
            paginator = self._ecs.get_paginator("list_services")
            service_arns: List[str] = []
            for page in paginator.paginate(cluster=cluster_arn):
                service_arns.extend(page.get("serviceArns", []))

            # Describe in batches of 10
            for i in range(0, len(service_arns), 10):
                batch = service_arns[i:i + 10]
                resp = self._ecs.describe_services(cluster=cluster_arn, services=batch)
                for svc in resp.get("services", []):
                    records.extend(self._collect_service(cluster_name, svc))

        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("ECS services failed for cluster %s: %s", cluster_name, exc)

        return records

    def _collect_service(self, cluster_name: str, svc: dict) -> List[MetricRecord]:
        """Collect metrics for a single ECS service."""
        records: List[MetricRecord] = []
        svc_name = svc.get("serviceName", "")
        svc_id   = f"{cluster_name}/{svc_name}"
        status   = svc.get("status", "UNKNOWN")

        base_dims = {
            "cluster":       cluster_name,
            "desired_count": svc.get("desiredCount", 0),
            "running_count": svc.get("runningCount", 0),
            "pending_count": svc.get("pendingCount", 0),
            "launch_type":   svc.get("launchType", ""),
        }

        records.append(self._make_record(
            resource_type="service",
            resource_id=svc_id,
            resource_name=svc_name,
            metric_name="service_status",
            metric_value=status,
            unit="none",
            dimensions=base_dims,
        ))

        records.append(self._make_record(
            resource_type="service",
            resource_id=svc_id,
            resource_name=svc_name,
            metric_name="running_task_count",
            metric_value=svc.get("runningCount", 0),
            unit="count",
            dimensions={"cluster": cluster_name},
        ))

        if status != "ACTIVE":
            return records

        end_time   = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        for cw_name, metric_name, unit in [
            ("CPUUtilization",    "cpu_utilization_percent",    "percent"),
            ("MemoryUtilization", "memory_utilization_percent", "percent"),
        ]:
            try:
                value = self._get_cw_metric(
                    cluster_name, svc_name, cw_name, start_time, end_time
                )
                if value is not None:
                    records.append(self._make_record(
                        resource_type="service",
                        resource_id=svc_id,
                        resource_name=svc_name,
                        metric_name=metric_name,
                        metric_value=round(value, 4),
                        unit=unit,
                        dimensions={"cluster": cluster_name},
                    ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.debug("CW %s failed for ECS %s: %s", cw_name, svc_name, exc)

        return records

    def _get_cw_metric(
        self,
        cluster_name: str,
        service_name: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace="AWS/ECS",
            MetricName=metric_name,
            Dimensions=[
                {"Name": "ClusterName", "Value": cluster_name},
                {"Name": "ServiceName", "Value": service_name},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get("Average")
