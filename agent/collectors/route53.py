"""Route53 hosted zone and health check collector (global)."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class Route53Collector(BaseCollector):
    """Collects Route53 hosted zone inventory and health check statuses.

    Route53 is a global service — should be run once with region='global'.
    """

    SERVICE_NAME = "route53"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._r53 = session.client("route53", region_name="us-east-1")
        self._cw = session.client("cloudwatch", region_name="us-east-1")

    def collect(self) -> List[MetricRecord]:
        """Collect Route53 hosted zones and health checks."""
        records: List[MetricRecord] = []
        try:
            records.extend(self._collect_hosted_zones())
            records.extend(self._collect_health_checks())
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("Route53 collection failed: %s", exc)
        return records

    def _collect_hosted_zones(self) -> List[MetricRecord]:
        """Collect hosted zone inventory."""
        records: List[MetricRecord] = []
        try:
            paginator = self._r53.get_paginator("list_hosted_zones")
            for page in paginator.paginate():
                for zone in page.get("HostedZones", []):
                    zone_id = zone.get("Id", "").split("/")[-1]
                    name = zone.get("Name", "")
                    private = zone.get("Config", {}).get("PrivateZone", False)
                    record_count = zone.get("ResourceRecordSetCount", 0)

                    records.append(self._make_record(
                        resource_type="hosted_zone",
                        resource_id=zone_id,
                        resource_name=name.rstrip("."),
                        metric_name="record_set_count",
                        metric_value=record_count,
                        unit="count",
                        dimensions={
                            "zone_name": name.rstrip("."),
                            "private_zone": str(private),
                        },
                    ))
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("Route53 hosted zones failed: %s", exc)
        return records

    def _collect_health_checks(self) -> List[MetricRecord]:
        """Collect health check statuses and CloudWatch metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._r53.get_paginator("list_health_checks")
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=10)

            for page in paginator.paginate():
                for hc in page.get("HealthChecks", []):
                    hc_id = hc.get("Id", "")
                    config = hc.get("HealthCheckConfig", {})
                    hc_type = config.get("Type", "")
                    fqdn = config.get("FullyQualifiedDomainName", "")
                    port = config.get("Port", "")
                    resource_path = config.get("ResourcePath", "")

                    base_dims = {
                        "type": hc_type,
                        "fqdn": fqdn,
                        "port": str(port),
                        "resource_path": resource_path,
                    }

                    # Health percentage from CloudWatch
                    try:
                        health_pct = self._get_cw_metric(
                            hc_id, "HealthCheckPercentageHealthy", start_time, end_time
                        )
                        if health_pct is not None:
                            records.append(self._make_record(
                                resource_type="health_check",
                                resource_id=hc_id,
                                resource_name=fqdn or hc_id,
                                metric_name="health_percentage",
                                metric_value=round(health_pct, 2),
                                unit="percent",
                                dimensions=base_dims,
                            ))

                        # Status (1 = healthy, 0 = unhealthy)
                        status_val = self._get_cw_metric(
                            hc_id, "HealthCheckStatus", start_time, end_time
                        )
                        status_str = "healthy" if (status_val or 0) >= 1 else "unhealthy"
                        records.append(self._make_record(
                            resource_type="health_check",
                            resource_id=hc_id,
                            resource_name=fqdn or hc_id,
                            metric_name="health_check_status",
                            metric_value=status_str,
                            unit="none",
                            dimensions=base_dims,
                        ))
                    except (ClientError, EndpointResolutionError) as exc:
                        logger.warning("CW health check metrics failed for %s: %s", hc_id, exc)

        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("Route53 health checks failed: %s", exc)
        return records

    def _get_cw_metric(
        self,
        hc_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace="AWS/Route53",
            MetricName=metric_name,
            Dimensions=[{"Name": "HealthCheckId", "Value": hc_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=["Average"],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get("Average")
