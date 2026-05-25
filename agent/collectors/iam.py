"""IAM risk summary collector — global service."""
import csv
import io
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class IAMCollector(BaseCollector):
    """Collects IAM risk indicators. Global service — region is always 'global'."""

    SERVICE_NAME = "iam"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        super().__init__(session, "global", customer_id)
        self._iam = session.client("iam", region_name="us-east-1")

    def collect(self) -> List[MetricRecord]:
        """Collect IAM risk summary metrics."""
        records: List[MetricRecord] = []
        try:
            records.extend(self._collect_credential_report())
            records.extend(self._collect_account_summary())
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "AccessDeniedException":
                logger.warning("IAM not accessible: %s", exc)
            else:
                logger.error("IAM collection failed: %s", exc)
        except EndpointResolutionError as exc:
            logger.warning("IAM endpoint error: %s", exc)
        return records

    def _collect_credential_report(self) -> List[MetricRecord]:
        """Parse the IAM credential report for MFA and key age issues."""
        records: List[MetricRecord] = []

        # Generate report (may take a few seconds)
        try:
            self._iam.generate_credential_report()
            for _ in range(10):
                resp = self._iam.generate_credential_report()
                if resp.get("State") == "COMPLETE":
                    break
                time.sleep(2)

            report_resp = self._iam.get_credential_report()
            content = report_resp.get("Content", b"").decode("utf-8")
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("Credential report unavailable: %s", exc)
            return records

        reader = csv.DictReader(io.StringIO(content))
        users_without_mfa = 0
        old_access_keys = 0
        root_mfa_active = True
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=90)

        for row in reader:
            username = row.get("user", "")

            if username == "<root_account>":
                root_mfa_active = row.get("mfa_active", "false").lower() == "true"
                continue

            if row.get("mfa_active", "false").lower() == "false" and \
               row.get("password_enabled", "false").lower() == "true":
                users_without_mfa += 1

            for key_num in ("1", "2"):
                active = row.get(f"access_key_{key_num}_active", "false").lower() == "true"
                last_rotated_str = row.get(f"access_key_{key_num}_last_rotated", "N/A")
                if active and last_rotated_str not in ("N/A", "no_information"):
                    try:
                        last_rotated = datetime.fromisoformat(
                            last_rotated_str.replace("Z", "+00:00")
                        )
                        if last_rotated < cutoff:
                            old_access_keys += 1
                    except ValueError:
                        pass

        records.append(self._make_record(
            resource_type="account",
            resource_id="iam",
            resource_name="iam_risk",
            metric_name="root_mfa_active",
            metric_value=str(root_mfa_active).lower(),
            unit="none",
        ))
        records.append(self._make_record(
            resource_type="account",
            resource_id="iam",
            resource_name="iam_risk",
            metric_name="users_without_mfa_count",
            metric_value=users_without_mfa,
            unit="count",
        ))
        records.append(self._make_record(
            resource_type="account",
            resource_id="iam",
            resource_name="iam_risk",
            metric_name="access_keys_older_than_90_days",
            metric_value=old_access_keys,
            unit="count",
        ))

        return records

    def _collect_account_summary(self) -> List[MetricRecord]:
        """Collect IAM account summary metrics."""
        records: List[MetricRecord] = []
        try:
            summary = self._iam.get_account_summary().get("SummaryMap", {})
            records.append(self._make_record(
                resource_type="account",
                resource_id="iam",
                resource_name="iam_summary",
                metric_name="total_users",
                metric_value=summary.get("Users", 0),
                unit="count",
            ))
            records.append(self._make_record(
                resource_type="account",
                resource_id="iam",
                resource_name="iam_summary",
                metric_name="total_roles",
                metric_value=summary.get("Roles", 0),
                unit="count",
            ))
        except (ClientError, EndpointResolutionError) as exc:
            logger.warning("IAM account summary failed: %s", exc)
        return records
