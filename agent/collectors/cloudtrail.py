"""CloudTrail high-risk event collector."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)

# High-risk event names to monitor
HIGH_RISK_EVENTS = {
    # IAM changes
    "CreateUser", "DeleteUser", "AttachUserPolicy", "DetachUserPolicy",
    "CreateAccessKey", "DeleteAccessKey", "UpdateAccessKey",
    "CreateRole", "DeleteRole", "AttachRolePolicy", "DetachRolePolicy",
    "PutUserPolicy", "PutRolePolicy", "DeleteUserPolicy", "DeleteRolePolicy",
    # Security group changes
    "AuthorizeSecurityGroupIngress", "AuthorizeSecurityGroupEgress",
    "RevokeSecurityGroupIngress", "RevokeSecurityGroupEgress",
    "CreateSecurityGroup", "DeleteSecurityGroup",
    # S3 policy changes
    "PutBucketPolicy", "DeleteBucketPolicy", "PutBucketAcl",
    "PutBucketPublicAccessBlock",
    # Network changes
    "CreateVpc", "DeleteVpc", "ModifyVpcAttribute",
    "CreateInternetGateway", "AttachInternetGateway",
    # Root account activity
    "ConsoleLogin",
    # KMS
    "DisableKey", "ScheduleKeyDeletion", "DeleteAlias",
    # CloudTrail itself
    "StopLogging", "DeleteTrail", "UpdateTrail",
}


class CloudTrailCollector(BaseCollector):
    """Collects recent high-risk CloudTrail events from the last 24 hours."""

    SERVICE_NAME = "cloudtrail"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._ct = session.client("cloudtrail", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect high-risk CloudTrail events from the last 24 hours."""
        records: List[MetricRecord] = []
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)

            paginator = self._ct.get_paginator("lookup_events")
            event_count = 0

            for page in paginator.paginate(
                StartTime=start_time,
                EndTime=end_time,
                MaxResults=50,
            ):
                for event in page.get("Events", []):
                    event_name = event.get("EventName", "")
                    if event_name not in HIGH_RISK_EVENTS:
                        continue

                    event_id = event.get("EventId", "")
                    event_time = event.get("EventTime", datetime.now(timezone.utc))
                    username = event.get("Username", "unknown")
                    source_ip = ""
                    resources = event.get("Resources", [])
                    resource_name = resources[0].get("ResourceName", "") if resources else ""

                    # Parse CloudTrail JSON for source IP
                    import json
                    try:
                        ct_event = json.loads(event.get("CloudTrailEvent", "{}"))
                        source_ip = ct_event.get("sourceIPAddress", "")
                    except (json.JSONDecodeError, TypeError):
                        pass

                    records.append(self._make_record(
                        resource_type="event",
                        resource_id=event_id,
                        resource_name=event_name,
                        metric_name="high_risk_event",
                        metric_value=event_name,
                        unit="none",
                        dimensions={
                            "event_name": event_name,
                            "username": username[:100],
                            "source_ip": source_ip,
                            "resource_name": resource_name[:100],
                            "event_time": event_time.isoformat() if hasattr(event_time, "isoformat") else str(event_time),
                        },
                    ))
                    event_count += 1
                    if event_count >= 50:
                        break
                if event_count >= 50:
                    break

            # Summary record
            records.append(self._make_record(
                resource_type="summary",
                resource_id=f"cloudtrail-{self.region}",
                resource_name=f"cloudtrail-{self.region}",
                metric_name="high_risk_events_24h",
                metric_value=event_count,
                unit="count",
            ))

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException",):
                logger.warning("CloudTrail not accessible in %s: %s", self.region, exc)
            else:
                logger.error("CloudTrail collection failed in %s: %s", self.region, exc)
        except EndpointResolutionError as exc:
            logger.warning("CloudTrail endpoint not available in %s: %s", self.region, exc)
        return records
