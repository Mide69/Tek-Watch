"""Unit tests for the CostExplorerCollector."""
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from collectors.cost_explorer import CostExplorerCollector


def make_daily_result(date_str="2026-01-01", amount="12.50", unit="USD"):
    return {
        "TimePeriod": {"Start": date_str, "End": "2026-01-02"},
        "Total": {"BlendedCost": {"Amount": amount, "Unit": unit}},
        "Groups": [],
    }


def make_service_group(service="Amazon EC2", amount="10.00"):
    return {
        "Keys": [service],
        "Metrics": {"BlendedCost": {"Amount": amount, "Unit": "USD"}},
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ce = MagicMock()
    session.client.return_value = ce
    c = CostExplorerCollector(session, "global", "TT-0001")
    c._ce = ce
    return c, ce


class TestCostExplorerCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "cost_explorer"

    def test_region_is_always_global(self, collector):
        c, _ = collector
        assert c.region == "global"

    def test_daily_cost_records_emitted(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [make_daily_result("2026-01-01", "12.50")]
        }
        ce.get_cost_forecast.return_value = {
            "Total": {"Amount": "300.00", "Unit": "USD"}
        }

        records = c.collect()
        daily = [r for r in records if r.metric_name == "daily_blended_cost"]
        assert len(daily) >= 1
        assert daily[0].metric_value == 12.5

    def test_daily_cost_dimensions_include_date(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [make_daily_result("2026-01-15")]
        }
        ce.get_cost_forecast.return_value = {"Total": {"Amount": "0", "Unit": "USD"}}

        records = c.collect()
        daily = next(r for r in records if r.metric_name == "daily_blended_cost")
        assert daily.dimensions["date"] == "2026-01-15"

    def test_service_breakdown_records_emitted(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.side_effect = [
            {"ResultsByTime": []},  # daily
            {"ResultsByTime": [{"TimePeriod": {}, "Groups": [make_service_group()]}]},  # breakdown
        ]
        ce.get_cost_forecast.return_value = {"Total": {"Amount": "0", "Unit": "USD"}}

        records = c.collect()
        breakdown = [r for r in records if r.metric_name == "mtd_blended_cost"]
        assert len(breakdown) == 1
        assert breakdown[0].resource_name == "Amazon EC2"

    def test_zero_cost_services_excluded(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.side_effect = [
            {"ResultsByTime": []},
            {"ResultsByTime": [{
                "TimePeriod": {},
                "Groups": [make_service_group("Unused Service", "0.00")],
            }]},
        ]
        ce.get_cost_forecast.return_value = {"Total": {"Amount": "0", "Unit": "USD"}}

        records = c.collect()
        breakdown = [r for r in records if r.metric_name == "mtd_blended_cost"]
        assert breakdown == []

    def test_forecast_record_emitted(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.return_value = {"ResultsByTime": []}
        ce.get_cost_forecast.return_value = {
            "Total": {"Amount": "450.75", "Unit": "USD"}
        }

        records = c.collect()
        forecast = [r for r in records if r.metric_name == "forecasted_monthly_cost"]
        assert len(forecast) == 1
        assert forecast[0].metric_value == 450.75

    def test_forecast_failure_does_not_stop_other_records(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [make_daily_result()]
        }
        ce.get_cost_forecast.side_effect = ClientError(
            {"Error": {"Code": "DataUnavailableException", "Message": "no data"}},
            "GetCostForecast",
        )

        records = c.collect()
        daily = [r for r in records if r.metric_name == "daily_blended_cost"]
        assert len(daily) >= 1

    def test_access_denied_returns_empty(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "GetCostAndUsage",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, ce = collector
        ce.get_cost_and_usage.return_value = {
            "ResultsByTime": [make_daily_result()]
        }
        ce.get_cost_forecast.return_value = {"Total": {"Amount": "100", "Unit": "USD"}}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
