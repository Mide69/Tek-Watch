"""Security Hub findings collector."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class SecurityHubCollector(BaseCollector):
    """Collects Security Hub active finding counts by severity and compliance standard."""

    SERVICE_NAME = "security_hub"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._sh = session.client("securityhub", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect Security Hub finding counts by severity."""
        records: List[MetricRecord] = []
        try:
            severity_counts = {
                "CRITICAL": 0,
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
                "INFORMATIONAL": 0,
            }

            paginator = self._sh.get_paginator("get_findings")
            for page in paginator.paginate(
                Filters={
                    "RecordState": [{"Value": "ACTIVE", "Comparison": "EQUALS"}],
                    "WorkflowStatus": [{"Value": "NEW", "Comparison": "EQUALS"}],
                },
                MaxResults=100,
            ):
                for finding in page.get("Findings", []):
                    severity = finding.get("Severity", {}).get("Label", "INFORMATIONAL")
                    if severity in severity_counts:
                        severity_counts[severity] += 1

            for severity, count in severity_counts.items():
                records.append(self._make_record(
                    resource_type="findings_summary",
                    resource_id=f"security-hub-{self.region}",
                    resource_name=f"security-hub-{self.region}",
                    metric_name=f"findings_{severity.lower()}_count",
                    metric_value=count,
                    unit="count",
                    dimensions={"severity": severity},
                ))

            total = sum(severity_counts.values())
            records.append(self._make_record(
                resource_type="findings_summary",
                resource_id=f"security-hub-{self.region}",
                resource_name=f"security-hub-{self.region}",
                metric_name="findings_total_count",
                metric_value=total,
                unit="count",
            ))

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException", "InvalidAccessException"):
                logger.warning("Security Hub not enabled/accessible in %s: %s", self.region, exc)
            else:
                logger.error("Security Hub collection failed in %s: %s", self.region, exc)
        except EndpointResolutionError as exc:
            logger.warning("Security Hub endpoint not available in %s: %s", self.region, exc)
        return records
