"""RDS instance inventory and performance metrics collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


def _as_dict(value) -> dict:
    """A response that is really a dict, or an empty one.

    Anything else, including a mock in a test or a partial response, counts as
    "not collected" so the caller leaves the dimension out.
    """
    return value if isinstance(value, dict) else {}


def _joined(values, limit: int = 10) -> str:
    """A list of ids as one dimension value, or "" when there is nothing real."""
    if not isinstance(values, (list, tuple)):
        return ""
    ids = [str(v) for v in values if isinstance(v, (str, int))]
    return ",".join(ids[:limit])


class RDSCollector(BaseCollector):
    """Collects RDS instance inventory and CloudWatch performance metrics."""

    SERVICE_NAME = "rds"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._rds = session.client("rds", region_name=region)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect RDS instance inventory and performance metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db in page.get("DBInstances", []):
                    records.extend(self._collect_instance(db))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("RDS collection failed in %s: %s", self.region, exc)
        return records

    def _collect_instance(self, db: dict) -> List[MetricRecord]:
        """Collect all metrics for a single RDS instance."""
        records: List[MetricRecord] = []
        db_id = db.get("DBInstanceIdentifier", "")
        engine = db.get("Engine", "")
        status = db.get("DBInstanceStatus", "")
        instance_class = db.get("DBInstanceClass", "")
        multi_az = db.get("MultiAZ", False)
        az = db.get("AvailabilityZone", "")
        allocated_storage_gb = db.get("AllocatedStorage", 0)

        base_dims = {
            "engine": engine,
            "engine_version": db.get("EngineVersion", ""),
            "instance_class": instance_class,
            "multi_az": str(multi_az),
            "az": az,
            "allocated_storage_gb": allocated_storage_gb,
            # Whether the database has a public endpoint. Nothing collected
            # this, so a database reachable from the internet looked exactly
            # like one that is not.
            "publicly_accessible": str(db.get("PubliclyAccessible", False)),
            # Days of automated backups, 0 meaning none. Operational resilience
            # rests on being able to restore, and nothing reported whether the
            # database could be.
            "backup_retention_days": db.get("BackupRetentionPeriod", 0),
        }
        subnet_group = _as_dict(db.get("DBSubnetGroup"))
        if subnet_group.get("VpcId"):
            base_dims["vpc_id"] = subnet_group["VpcId"]
        groups = _joined([
            g.get("VpcSecurityGroupId") for g in db.get("VpcSecurityGroups", []) or []
            if isinstance(g, dict)
        ])
        if groups:
            base_dims["security_groups"] = groups

        # Inventory record
        records.append(self._make_record(
            resource_type="db_instance",
            resource_id=db_id,
            resource_name=db_id,
            metric_name="db_instance_status",
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
            ("DatabaseConnections", "database_connections",     "count"),
            ("FreeStorageSpace",    "free_storage_bytes",       "bytes"),
            ("ReadIOPS",            "read_iops",                "count"),
            ("WriteIOPS",           "write_iops",               "count"),
            ("ReadLatency",         "read_latency_seconds",     "seconds"),
            ("WriteLatency",        "write_latency_seconds",    "seconds"),
        ]

        free_storage_bytes: Optional[float] = None

        for cw_name, metric_name, unit in cw_metrics:
            try:
                value = self._get_cw_metric(db_id, cw_name, start_time, end_time)
                if value is not None:
                    if metric_name == "free_storage_bytes":
                        free_storage_bytes = value
                    records.append(self._make_record(
                        resource_type="db_instance",
                        resource_id=db_id,
                        resource_name=db_id,
                        metric_name=metric_name,
                        metric_value=round(value, 4),
                        unit=unit,
                        dimensions=base_dims,
                    ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.warning("CloudWatch %s failed for RDS %s: %s", cw_name, db_id, exc)

        # Derived: storage_used_percent
        if free_storage_bytes is not None and allocated_storage_gb > 0:
            allocated_bytes = allocated_storage_gb * 1024 ** 3
            used_pct = round((1 - free_storage_bytes / allocated_bytes) * 100, 2)
            storage_warning = used_pct > 90
            records.append(self._make_record(
                resource_type="db_instance",
                resource_id=db_id,
                resource_name=db_id,
                metric_name="storage_used_percent",
                metric_value=used_pct,
                unit="percent",
                dimensions={**base_dims, "storage_warning": str(storage_warning)},
            ))

        return records

    def _get_cw_metric(
        self,
        db_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        """Fetch the latest CloudWatch metric value for an RDS instance."""
        response = self._cw.get_metric_statistics(
            Namespace="AWS/RDS",
            MetricName=metric_name,
            Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get("Average")
