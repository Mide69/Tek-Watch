"""S3 bucket inventory and metrics collector (global)."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class S3Collector(BaseCollector):
    """Collects S3 bucket inventory and CloudWatch storage metrics.

    S3 is a global service — should be run once with region='global'.
    """

    SERVICE_NAME = "s3"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, "global", customer_id)
        self._s3 = session.client("s3", region_name="us-east-1")
        self._cw = session.client("cloudwatch", region_name="us-east-1")

    def collect(self) -> List[MetricRecord]:
        """Collect S3 bucket inventory and storage metrics."""
        records: List[MetricRecord] = []
        try:
            buckets = self._s3.list_buckets().get("Buckets", [])
            for bucket in buckets:
                records.extend(self._collect_bucket(bucket))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("S3 collection failed: %s", exc)
        return records

    def _collect_bucket(self, bucket: dict) -> List[MetricRecord]:
        """Collect metrics for a single S3 bucket."""
        records: List[MetricRecord] = []
        name = bucket.get("Name", "")

        # Bucket region
        bucket_region = "us-east-1"
        try:
            loc = self._s3.get_bucket_location(Bucket=name)
            bucket_region = loc.get("LocationConstraint") or "us-east-1"
        except (ClientError, EndpointResolutionError):
            pass

        # Versioning status
        versioning = "Disabled"
        try:
            v = self._s3.get_bucket_versioning(Bucket=name)
            versioning = v.get("Status", "Disabled") or "Disabled"
        except (ClientError, EndpointResolutionError):
            pass

        # Encryption status, and which algorithm. The dashboard names the
        # algorithm next to the padlock, so "encrypted: true" was never enough
        # to render the column it was collected for.
        encryption_enabled = False
        encryption_algorithm = ""
        try:
            enc = self._s3.get_bucket_encryption(Bucket=name)
            rules = (
                enc.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
            )
            for rule in rules:
                algorithm = (
                    rule.get("ApplyServerSideEncryptionByDefault", {})
                    .get("SSEAlgorithm", "")
                )
                if algorithm:
                    encryption_enabled = True
                    encryption_algorithm = algorithm
                    break
        except (ClientError, EndpointResolutionError):
            pass  # No configuration, or no permission to read it — not encrypted

        # Public access block. This is the single most consequential fact about
        # a bucket and the storage page has a column for it, but nothing
        # collected it, so every bucket was about to be labelled Public on the
        # strength of a missing field.
        public_access_blocked: Optional[bool] = None
        try:
            cfg = self._s3.get_public_access_block(Bucket=name)
            block = cfg.get("PublicAccessBlockConfiguration", {})
            public_access_blocked = all(
                bool(block.get(key))
                for key in (
                    "BlockPublicAcls",
                    "IgnorePublicAcls",
                    "BlockPublicPolicy",
                    "RestrictPublicBuckets",
                )
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code == "NoSuchPublicAccessBlockConfiguration":
                public_access_blocked = False
            # Any other error means we could not determine it. Leave it unknown
            # rather than guessing, in either direction: claiming a bucket is
            # blocked when it is not is dangerous, and claiming it is public
            # when it is not trains people to ignore the warning.
        except EndpointResolutionError:
            pass

        base_dims = {
            "bucket_region":       bucket_region,
            "versioning_enabled":  str(versioning == "Enabled"),
            "encryption_enabled":  str(encryption_enabled),
            "encryption_algorithm": encryption_algorithm,
        }
        if public_access_blocked is not None:
            base_dims["public_access_blocked"] = str(public_access_blocked)

        # Inventory record
        records.append(self._make_record(
            resource_type="bucket",
            resource_id=name,
            resource_name=name,
            metric_name="bucket_state",
            metric_value="active",
            unit="none",
            dimensions=base_dims,
        ))

        end_time   = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=2)  # S3 metrics are daily

        # Bucket size
        size = self._get_cw_metric(
            name, "BucketSizeBytes", "StandardStorage", start_time, end_time
        )
        if size is not None:
            records.append(self._make_record(
                resource_type="bucket",
                resource_id=name,
                resource_name=name,
                metric_name="bucket_size_bytes",
                metric_value=round(size, 0),
                unit="bytes",
                dimensions=base_dims,
            ))

        # Object count
        obj_count = self._get_cw_metric(
            name, "NumberOfObjects", "AllStorageTypes", start_time, end_time
        )
        if obj_count is not None:
            records.append(self._make_record(
                resource_type="bucket",
                resource_id=name,
                resource_name=name,
                metric_name="number_of_objects",
                metric_value=int(obj_count),
                unit="count",
                dimensions=base_dims,
            ))

        return records

    def _get_cw_metric(
        self,
        bucket_name: str,
        metric_name: str,
        storage_type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[float]:
        try:
            response = self._cw.get_metric_statistics(
                Namespace="AWS/S3",
                MetricName=metric_name,
                Dimensions=[
                    {"Name": "BucketName",   "Value": bucket_name},
                    {"Name": "StorageType",  "Value": storage_type},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Average"],
            )
            datapoints = response.get("Datapoints", [])
            if not datapoints:
                return None
            return max(datapoints, key=lambda d: d["Timestamp"]).get("Average")
        except (ClientError, EndpointResolutionError):
            return None
