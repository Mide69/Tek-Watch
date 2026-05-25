"""GuardDuty findings collector."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class GuardDutyCollector(BaseCollector):
    """Collects GuardDuty finding counts and top findings by severity."""

    SERVICE_NAME = "guardduty"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._gd = session.client("guardduty", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect GuardDuty finding counts and top 10 findings."""
        records: List[MetricRecord] = []
        try:
            detectors = self._gd.list_detectors().get("DetectorIds", [])
            if not detectors:
                logger.info("No GuardDuty detectors in %s", self.region)
                return records

            detector_id = detectors[0]
            records.extend(self._collect_findings(detector_id))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException", "BadRequestException"):
                logger.warning("GuardDuty not accessible in %s: %s", self.region, exc)
            else:
                logger.error("GuardDuty collection failed in %s: %s", self.region, exc)
        except EndpointResolutionError as exc:
            logger.warning("GuardDuty endpoint not available in %s: %s", self.region, exc)
        return records

    def _collect_findings(self, detector_id: str) -> List[MetricRecord]:
        """Collect finding counts by severity and top 10 findings."""
        records: List[MetricRecord] = []

        severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}

        # Get finding IDs (paginated)
        finding_ids: List[str] = []
        paginator = self._gd.get_paginator("list_findings")
        for page in paginator.paginate(DetectorId=detector_id):
            finding_ids.extend(page.get("FindingIds", []))

        if not finding_ids:
            for severity, count in severity_counts.items():
                records.append(self._make_record(
                    resource_type="detector",
                    resource_id=detector_id,
                    resource_name=f"guardduty-{self.region}",
                    metric_name=f"findings_{severity.lower()}_count",
                    metric_value=0,
                    unit="count",
                ))
            return records

        # Fetch details in batches of 50
        all_findings = []
        for i in range(0, len(finding_ids), 50):
            batch = finding_ids[i:i + 50]
            response = self._gd.get_findings(DetectorId=detector_id, FindingIds=batch)
            all_findings.extend(response.get("Findings", []))

        # Count by severity
        for finding in all_findings:
            sev_score = finding.get("Severity", 0)
            if sev_score >= 9:
                severity_counts["CRITICAL"] += 1
            elif sev_score >= 7:
                severity_counts["HIGH"] += 1
            elif sev_score >= 4:
                severity_counts["MEDIUM"] += 1
            else:
                severity_counts["LOW"] += 1

        for severity, count in severity_counts.items():
            records.append(self._make_record(
                resource_type="detector",
                resource_id=detector_id,
                resource_name=f"guardduty-{self.region}",
                metric_name=f"findings_{severity.lower()}_count",
                metric_value=count,
                unit="count",
            ))

        # Top 10 findings as individual records
        top_findings = sorted(
            all_findings, key=lambda f: f.get("Severity", 0), reverse=True
        )[:10]

        for finding in top_findings:
            records.append(self._make_record(
                resource_type="finding",
                resource_id=finding.get("Id", ""),
                resource_name=finding.get("Title", "")[:100],
                metric_name="finding_severity",
                metric_value=finding.get("Severity", 0),
                unit="none",
                dimensions={
                    "type": finding.get("Type", ""),
                    "resource_type": finding.get("Resource", {}).get("ResourceType", ""),
                    "created_at": finding.get("CreatedAt", ""),
                },
            ))

        return records
