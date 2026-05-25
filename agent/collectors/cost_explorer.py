"""Cost Explorer — daily spend, per-service breakdown, and forecast collector."""
import logging
from datetime import date, timedelta
from typing import List

import boto3
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.base import BaseCollector, MetricRecord

logger = logging.getLogger(__name__)


class CostExplorerCollector(BaseCollector):
    """Collects AWS Cost Explorer data. Global service — region is always 'global'."""

    SERVICE_NAME = "cost_explorer"

    def __init__(self, session: boto3.Session, region: str, customer_id: str) -> None:
        # Cost Explorer is a global service; always use us-east-1 endpoint
        super().__init__(session, "global", customer_id)
        self._ce = session.client("ce", region_name="us-east-1")

    def collect(self) -> List[MetricRecord]:
        """Collect daily costs, per-service breakdown, and 30-day forecast."""
        records: List[MetricRecord] = []
        try:
            records.extend(self._collect_daily_costs())
            records.extend(self._collect_service_breakdown())
            records.extend(self._collect_forecast())
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException", "OptInRequired"):
                logger.warning("Cost Explorer not accessible: %s", exc)
            else:
                logger.error("Cost Explorer collection failed: %s", exc)
        except EndpointResolutionError as exc:
            logger.warning("Cost Explorer endpoint error: %s", exc)
        return records

    def _collect_daily_costs(self) -> List[MetricRecord]:
        """Collect daily BlendedCost for the last 30 days."""
        records: List[MetricRecord] = []
        end = date.today()
        start = end - timedelta(days=30)

        response = self._ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["BlendedCost"],
        )

        for result in response.get("ResultsByTime", []):
            period_start = result.get("TimePeriod", {}).get("Start", "")
            amount = float(result.get("Total", {}).get("BlendedCost", {}).get("Amount", 0))
            unit = result.get("Total", {}).get("BlendedCost", {}).get("Unit", "USD")

            records.append(self._make_record(
                resource_type="account",
                resource_id=self.customer_id,
                resource_name="daily_cost",
                metric_name="daily_blended_cost",
                metric_value=round(amount, 4),
                unit=unit.lower(),
                dimensions={"date": period_start},
            ))

        return records

    def _collect_service_breakdown(self) -> List[MetricRecord]:
        """Collect month-to-date cost grouped by AWS service."""
        records: List[MetricRecord] = []
        today = date.today()
        start = today.replace(day=1)

        response = self._ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": today.isoformat()},
            Granularity="MONTHLY",
            Metrics=["BlendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                service_name = group.get("Keys", ["unknown"])[0]
                amount = float(group.get("Metrics", {}).get("BlendedCost", {}).get("Amount", 0))
                unit = group.get("Metrics", {}).get("BlendedCost", {}).get("Unit", "USD")

                if amount > 0:
                    records.append(self._make_record(
                        resource_type="service_cost",
                        resource_id=service_name.replace(" ", "_").lower(),
                        resource_name=service_name,
                        metric_name="mtd_blended_cost",
                        metric_value=round(amount, 4),
                        unit=unit.lower(),
                        dimensions={"aws_service": service_name},
                    ))

        return records

    def _collect_forecast(self) -> List[MetricRecord]:
        """Collect 30-day cost forecast."""
        records: List[MetricRecord] = []
        today = date.today()
        end = today + timedelta(days=30)

        try:
            response = self._ce.get_cost_forecast(
                TimePeriod={"Start": today.isoformat(), "End": end.isoformat()},
                Metric="BLENDED_COST",
                Granularity="MONTHLY",
            )
            amount = float(response.get("Total", {}).get("Amount", 0))
            unit = response.get("Total", {}).get("Unit", "USD")

            records.append(self._make_record(
                resource_type="account",
                resource_id=self.customer_id,
                resource_name="cost_forecast",
                metric_name="forecasted_monthly_cost",
                metric_value=round(amount, 4),
                unit=unit.lower(),
                dimensions={"forecast_period_days": 30},
            ))
        except ClientError as exc:
            logger.warning("Cost forecast failed: %s", exc)

        return records
