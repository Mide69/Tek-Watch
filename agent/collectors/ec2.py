"""EC2 instance inventory and performance metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)

_CW_PERIOD = 300       # 5-minute CloudWatch period
_CW_STAT = "Average"


class EC2Collector(BaseCollector):
    """Collects EC2 instance inventory and CloudWatch performance metrics."""

    SERVICE_NAME = "ec2"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._ec2 = session.client("ec2", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect EC2 instance inventory and CPU/network/status metrics."""
        records: List[MetricRecord] = []
        try:
            instances = self._get_all_instances()
            for instance in instances:
                records.extend(self._collect_instance(instance))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("EC2 collection failed in %s: %s", self.region, exc)
        return records

    def _get_all_instances(self) -> list:
        """Paginate through all EC2 instances in the region."""
        instances = []
        paginator = self._ec2.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                instances.extend(reservation.get("Instances", []))
        return instances

    def _get_tag(self, tags: list, key: str, default: str = "") -> str:
        """Extract a tag value by key from an EC2 tags list."""
        for tag in tags or []:
            if tag.get("Key") == key:
                return tag.get("Value", default)
        return default

    def _collect_instance(self, instance: dict) -> List[MetricRecord]:
        """Collect all metrics for a single EC2 instance."""
        records: List[MetricRecord] = []
        instance_id = instance.get("InstanceId", "")
        name = self._get_tag(instance.get("Tags", []), "Name", instance_id)
        state = instance.get("State", {}).get("Name", "unknown")
        instance_type = instance.get("InstanceType", "")
        az = instance.get("Placement", {}).get("AvailabilityZone", "")

        base_dims = {
            "instance_type": instance_type,
            "state": state,
            "az": az,
            "vpc_id": instance.get("VpcId", ""),
            "subnet_id": instance.get("SubnetId", ""),
        }

        # Inventory record
        records.append(self._make_record(
            resource_type="instance",
            resource_id=instance_id,
            resource_name=name,
            metric_name="instance_state",
            metric_value=state,
            unit="none",
            dimensions=base_dims,
        ))

        # Only collect CloudWatch metrics for running instances
        if state != "running":
            return records

        cw_metrics = [
            ("CPUUtilization",          "cpu_utilization_percent",    "percent"),
            ("NetworkIn",               "network_in_bytes",           "bytes"),
            ("NetworkOut",              "network_out_bytes",          "bytes"),
            ("StatusCheckFailed_Instance", "status_check_failed_instance", "count"),
            ("StatusCheckFailed_System",   "status_check_failed_system",   "count"),
        ]

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        for cw_name, metric_name, unit in cw_metrics:
            try:
                value = self._get_cw_metric(instance_id, cw_name, start_time, end_time)
                if value is not None:
                    records.append(self._make_record(
                        resource_type="instance",
                        resource_id=instance_id,
                        resource_name=name,
                        metric_name=metric_name,
                        metric_value=round(value, 4),
                        unit=unit,
                        dimensions=base_dims,
                    ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.warning(
                    "CloudWatch metric %s failed for %s: %s", cw_name, instance_id, exc
                )

        return records

    def _get_cw_metric(
        self,
        instance_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> float | None:
        """Fetch the latest CloudWatch metric value for an EC2 instance."""
        response = self._cw.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName=metric_name,
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=_CW_PERIOD,
            Statistics=[_CW_STAT],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        latest = max(datapoints, key=lambda d: d["Timestamp"])
        return latest.get(_CW_STAT)
