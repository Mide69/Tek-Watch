"""CloudFront distribution inventory and metrics collector (global)."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class CloudFrontCollector(BaseCollector):
    """Collects CloudFront distribution inventory and performance metrics.

    CloudFront is a global service — metrics are in us-east-1 regardless of region.
    This collector should be run once with region='global'.
    """

    SERVICE_NAME = "cloudfront"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        # CloudFront API is global; metrics are in us-east-1
        self._cf = session.client("cloudfront", region_name="us-east-1")
        self._cw = session.client("cloudwatch", region_name="us-east-1")

    def collect(self) -> List[MetricRecord]:
        """Collect CloudFront distribution inventory and metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._cf.get_paginator("list_distributions")
            for page in paginator.paginate():
                dist_list = page.get("DistributionList", {})
                for dist in dist_list.get("Items", []):
                    records.extend(self._collect_distribution(dist))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("CloudFront collection failed: %s", exc)
        return records

    def _collect_distribution(self, dist: dict) -> List[MetricRecord]:
        """Collect metrics for a single CloudFront distribution."""
        records: List[MetricRecord] = []
        dist_id = dist.get("Id", "")
        domain = dist.get("DomainName", "")
        status = dist.get("Status", "unknown")
        enabled = dist.get("Enabled", False)
        price_class = dist.get("PriceClass", "")

        # Get aliases (CNAMEs)
        aliases = dist.get("Aliases", {}).get("Items", [])
        alias_str = ",".join(aliases[:3]) if aliases else domain

        base_dims = {
            "domain": domain,
            "price_class": price_class,
            "enabled": str(enabled),
            "aliases": alias_str,
        }

        records.append(self._make_record(
            resource_type="distribution",
            resource_id=dist_id,
            resource_name=alias_str or domain,
            metric_name="distribution_status",
            metric_value=status,
            unit="none",
            dimensions=base_dims,
        ))

        if status != "Deployed" or not enabled:
            return records

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=10)

        for cw_name, metric_name, unit, stat in [
            ("Requests",        "requests",             "count",   "Sum"),
            ("BytesDownloaded", "bytes_downloaded",     "bytes",   "Sum"),
            ("BytesUploaded",   "bytes_uploaded",       "bytes",   "Sum"),
            ("4xxErrorRate",    "error_rate_4xx",       "percent", "Average"),
            ("5xxErrorRate",    "error_rate_5xx",       "percent", "Average"),
            ("TotalErrorRate",  "total_error_rate",     "percent", "Average"),
            ("CacheHitRate",    "cache_hit_rate",       "percent", "Average"),
        ]:
            try:
                value = self._get_cw_metric(dist_id, cw_name, start_time, end_time, stat)
                if value is not None:
                    records.append(self._make_record(
                        resource_type="distribution",
                        resource_id=dist_id,
                        resource_name=alias_str or domain,
                        metric_name=metric_name,
                        metric_value=round(value, 4),
                        unit=unit,
                        dimensions=base_dims,
                    ))
            except (ClientError, EndpointResolutionError) as exc:
                logger.warning("CW %s failed for CF dist %s: %s", cw_name, dist_id, exc)

        return records

    def _get_cw_metric(
        self,
        dist_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        stat: str = "Average",
    ) -> Optional[float]:
        response = self._cw.get_metric_statistics(
            Namespace="AWS/CloudFront",
            MetricName=metric_name,
            Dimensions=[
                {"Name": "DistributionId", "Value": dist_id},
                {"Name": "Region", "Value": "Global"},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=[stat],
        )
        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None
        return max(datapoints, key=lambda d: d["Timestamp"]).get(stat)
