"""ACM certificate inventory and expiry collector."""
import logging
from datetime import datetime, timezone
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class ACMCollector(BaseCollector):
    """Collects ACM certificate inventory and days-until-expiry."""

    SERVICE_NAME = "acm"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._acm = session.client("acm", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect ACM certificate inventory and expiry metrics."""
        records: List[MetricRecord] = []
        try:
            paginator = self._acm.get_paginator("list_certificates")
            for page in paginator.paginate():
                for cert_summary in page.get("CertificateSummaryList", []):
                    records.extend(self._collect_certificate(cert_summary))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDeniedException":
                logger.warning("ACM not accessible in %s: %s", self.region, exc)
            else:
                logger.error("ACM collection failed in %s: %s", self.region, exc)
        except EndpointResolutionError as exc:
            logger.warning("ACM endpoint not available in %s: %s", self.region, exc)
        return records

    def _collect_certificate(self, cert_summary: dict) -> List[MetricRecord]:
        """Collect metrics for a single ACM certificate."""
        records: List[MetricRecord] = []
        cert_arn = cert_summary.get("CertificateArn", "")
        domain = cert_summary.get("DomainName", "")

        try:
            detail = self._acm.describe_certificate(CertificateArn=cert_arn)
            cert = detail.get("Certificate", {})
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("Failed to describe certificate %s: %s", cert_arn, exc)
            return records

        expiry = cert.get("NotAfter")
        status = cert.get("Status", "UNKNOWN")
        now = datetime.now(timezone.utc)

        days_until_expiry = -1
        if expiry:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            days_until_expiry = max(0, (expiry - now).days)

        dims = {
            "domain": domain,
            "status": status,
            "type": cert.get("Type", ""),
            "expiry_date": expiry.isoformat() if expiry else "",
        }

        records.append(self._make_record(
            resource_type="certificate",
            resource_id=cert_arn,
            resource_name=domain,
            metric_name="days_until_expiry",
            metric_value=days_until_expiry,
            unit="days",
            dimensions=dims,
        ))

        records.append(self._make_record(
            resource_type="certificate",
            resource_id=cert_arn,
            resource_name=domain,
            metric_name="certificate_status",
            metric_value=status,
            unit="none",
            dimensions=dims,
        ))

        return records
