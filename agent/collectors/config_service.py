"""AWS Config compliance collector."""
import logging
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class ConfigServiceCollector(BaseCollector):
    """Collects AWS Config compliance rule results."""

    SERVICE_NAME = "config"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, region, customer_id)
        self._config = session.client("config", region_name=region)

    def collect(self) -> List[MetricRecord]:
        """Collect AWS Config compliance summary and non-compliant rules."""
        records: List[MetricRecord] = []
        try:
            compliant = 0
            non_compliant = 0
            insufficient_data = 0

            paginator = self._config.get_paginator("describe_compliance_by_config_rule")
            for page in paginator.paginate():
                for rule in page.get("ComplianceByConfigRules", []):
                    rule_name = rule.get("ConfigRuleName", "")
                    compliance = rule.get("Compliance", {})
                    compliance_type = compliance.get("ComplianceType", "NOT_APPLICABLE")

                    if compliance_type == "COMPLIANT":
                        compliant += 1
                    elif compliance_type == "NON_COMPLIANT":
                        non_compliant += 1
                        # Record individual non-compliant rule
                        records.append(self._make_record(
                            resource_type="config_rule",
                            resource_id=rule_name,
                            resource_name=rule_name,
                            metric_name="compliance_status",
                            metric_value="NON_COMPLIANT",
                            unit="none",
                            dimensions={"compliance_type": compliance_type},
                        ))
                    elif compliance_type == "INSUFFICIENT_DATA":
                        insufficient_data += 1

            # Summary records
            records.append(self._make_record(
                resource_type="compliance_summary",
                resource_id=f"config-{self.region}",
                resource_name=f"config-{self.region}",
                metric_name="compliant_rules_count",
                metric_value=compliant,
                unit="count",
            ))
            records.append(self._make_record(
                resource_type="compliance_summary",
                resource_id=f"config-{self.region}",
                resource_name=f"config-{self.region}",
                metric_name="non_compliant_rules_count",
                metric_value=non_compliant,
                unit="count",
            ))

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException", "NoSuchConfigurationRecorderException"):
                logger.warning("AWS Config not enabled/accessible in %s: %s", self.region, exc)
            else:
                logger.error("AWS Config collection failed in %s: %s", self.region, exc)
        except EndpointResolutionError as exc:
            logger.warning("AWS Config endpoint not available in %s: %s", self.region, exc)
        return records
