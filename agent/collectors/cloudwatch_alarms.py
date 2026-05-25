"""CloudWatch Alarms inventory collector."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class CloudWatchAlarmsCollector(BaseCollector):
    """Collects full CloudWatch alarm inventory with current state."""

    SERVICE_NAME = "cloudwatch_alarms"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._cw = session.client("cloudwatch", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect all CloudWatch alarms and their current state."""
        records: List[MetricRecord] = []
        try:
            paginator = self._cw.get_paginator("describe_alarms")
            for page in paginator.paginate(AlarmTypes=["MetricAlarm"]):
                for alarm in page.get("MetricAlarms", []):
                    records.append(self._alarm_to_record(alarm))
        except (ClientError, EndpointResolutionError) as exc:
            logger.error("CloudWatch Alarms collection failed in %s: %s", self.region, exc)
        return records

    def _alarm_to_record(self, alarm: dict) -> MetricRecord:
        """Convert a CloudWatch alarm dict to a MetricRecord."""
        alarm_name = alarm.get("AlarmName", "")
        state = alarm.get("StateValue", "UNKNOWN")
        metric_name = alarm.get("MetricName", "")
        namespace = alarm.get("Namespace", "")
        threshold = alarm.get("Threshold", 0)
        comparison = alarm.get("ComparisonOperator", "")
        last_updated = alarm.get("StateUpdatedTimestamp", "")

        return self._make_record(
            resource_type="alarm",
            resource_id=alarm.get("AlarmArn", alarm_name),
            resource_name=alarm_name,
            metric_name="alarm_state",
            metric_value=state,
            unit="none",
            dimensions={
                "metric_name": metric_name,
                "namespace": namespace,
                "threshold": threshold,
                "comparison_operator": comparison,
                "last_state_change": last_updated.isoformat() if hasattr(last_updated, "isoformat") else str(last_updated),
            },
        )
