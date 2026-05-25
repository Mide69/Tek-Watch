"""Trusted Advisor check results collector (requires Business/Enterprise support)."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)

# Trusted Advisor categories
TA_CATEGORIES = ["cost_optimizing", "performance", "security", "fault_tolerance", "service_limits"]


class TrustedAdvisorCollector(BaseCollector):
    """Collects Trusted Advisor check results across all five categories.

    Requires Business or Enterprise AWS Support plan.
    Gracefully skips if not available.
    """

    SERVICE_NAME = "trusted_advisor"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        # Support API is only available in us-east-1
        self._support = session.client("support", region_name="us-east-1")

    def collect(self) -> List[MetricRecord]:
        """Collect Trusted Advisor check results."""
        records: List[MetricRecord] = []
        try:
            # Get all available checks
            response = self._support.describe_trusted_advisor_checks(language="en")
            checks = response.get("checks", [])

            if not checks:
                logger.info("No Trusted Advisor checks available (may require Business support)")
                return records

            # Group checks by category
            category_counts = {cat: {"ok": 0, "warning": 0, "error": 0} for cat in TA_CATEGORIES}

            for check in checks:
                check_id = check.get("id", "")
                check_name = check.get("name", "")
                category = check.get("category", "").lower().replace(" ", "_")

                try:
                    result_response = self._support.describe_trusted_advisor_check_result(
                        checkId=check_id, language="en"
                    )
                    result = result_response.get("result", {})
                    status = result.get("status", "not_available")

                    if status in ("ok", "warning", "error") and category in category_counts:
                        category_counts[category][status] += 1

                    # Record individual check result
                    records.append(self._make_record(
                        resource_type="check",
                        resource_id=check_id,
                        resource_name=check_name[:100],
                        metric_name="check_status",
                        metric_value=status,
                        unit="none",
                        dimensions={"category": category},
                    ))

                except ClientError as exc:
                    logger.debug("TA check %s result failed: %s", check_id, exc)

            # Summary per category
            for category, counts in category_counts.items():
                for status, count in counts.items():
                    records.append(self._make_record(
                        resource_type="category_summary",
                        resource_id=f"trusted-advisor-{category}",
                        resource_name=category,
                        metric_name=f"{status}_checks_count",
                        metric_value=count,
                        unit="count",
                        dimensions={"category": category},
                    ))

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("SubscriptionRequiredException",):
                logger.info("Trusted Advisor requires Business/Enterprise support plan — skipping")
            else:
                logger.error("Trusted Advisor collection failed: %s", exc)
        except EndpointResolutionError as exc:
            logger.warning("Trusted Advisor endpoint not available: %s", exc)
        return records
