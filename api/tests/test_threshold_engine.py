"""Unit tests for the threshold evaluation engine."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.alerting.threshold import _evaluate, evaluate_thresholds_for_customer


class TestEvaluate:
    def test_gt_true(self):
        assert _evaluate(90.0, "gt", 85.0) is True

    def test_gt_false(self):
        assert _evaluate(80.0, "gt", 85.0) is False

    def test_gt_equal_false(self):
        assert _evaluate(85.0, "gt", 85.0) is False

    def test_gte_equal_true(self):
        assert _evaluate(85.0, "gte", 85.0) is True

    def test_lt_true(self):
        assert _evaluate(5.0, "lt", 10.0) is True

    def test_lt_false(self):
        assert _evaluate(15.0, "lt", 10.0) is False

    def test_lte_equal_true(self):
        assert _evaluate(10.0, "lte", 10.0) is True

    def test_unknown_operator_returns_false(self):
        assert _evaluate(100.0, "eq", 100.0) is False


@pytest.mark.asyncio
async def test_evaluate_thresholds_creates_alert():
    ts_service = MagicMock()
    db_service = MagicMock()
    notif_service = MagicMock()
    notif_service.send_ops_alert = AsyncMock()

    # Default threshold: ec2 cpu > 85 → high
    db_service.get_thresholds.side_effect = lambda cid: (
        [{"service": "ec2", "metric_name": "cpu_utilization_percent",
          "operator": "gt", "threshold_value": 85, "severity": "high", "enabled": True}]
        if cid == "DEFAULT" else []
    )
    db_service.get_alerts.return_value = []
    db_service.create_alert.return_value = "alert-001"

    # Resource with CPU at 91% (above threshold)
    ts_service.get_resources_by_service.return_value = [
        {"resource_id": "i-abc", "resource_name": "web-server",
         "metric_name": "cpu_utilization_percent", "value": "91.0"}
    ]

    count = await evaluate_thresholds_for_customer(
        "TT-0001", ts_service, db_service, notif_service
    )

    assert count == 1
    db_service.create_alert.assert_called_once()
    notif_service.send_ops_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_thresholds_no_breach():
    ts_service = MagicMock()
    db_service = MagicMock()
    notif_service = MagicMock()
    notif_service.send_ops_alert = AsyncMock()

    db_service.get_thresholds.side_effect = lambda cid: (
        [{"service": "ec2", "metric_name": "cpu_utilization_percent",
          "operator": "gt", "threshold_value": 85, "severity": "high", "enabled": True}]
        if cid == "DEFAULT" else []
    )
    db_service.get_alerts.return_value = []

    # CPU at 50% — below threshold
    ts_service.get_resources_by_service.return_value = [
        {"resource_id": "i-abc", "metric_name": "cpu_utilization_percent", "value": "50.0"}
    ]

    count = await evaluate_thresholds_for_customer(
        "TT-0001", ts_service, db_service, notif_service
    )

    assert count == 0
    db_service.create_alert.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_thresholds_skips_existing_alert():
    ts_service = MagicMock()
    db_service = MagicMock()
    notif_service = MagicMock()
    notif_service.send_ops_alert = AsyncMock()

    db_service.get_thresholds.side_effect = lambda cid: (
        [{"service": "ec2", "metric_name": "cpu_utilization_percent",
          "operator": "gt", "threshold_value": 85, "severity": "high", "enabled": True}]
        if cid == "DEFAULT" else []
    )
    # Alert already exists for this resource+metric
    db_service.get_alerts.return_value = [
        {"service": "ec2", "resource_id": "i-abc",
         "metric_name": "cpu_utilization_percent", "status": "active"}
    ]

    ts_service.get_resources_by_service.return_value = [
        {"resource_id": "i-abc", "metric_name": "cpu_utilization_percent", "value": "91.0"}
    ]

    count = await evaluate_thresholds_for_customer(
        "TT-0001", ts_service, db_service, notif_service
    )

    assert count == 0  # No new alert — already exists


@pytest.mark.asyncio
async def test_evaluate_thresholds_disabled_threshold_skipped():
    ts_service = MagicMock()
    db_service = MagicMock()
    notif_service = MagicMock()
    notif_service.send_ops_alert = AsyncMock()

    db_service.get_thresholds.side_effect = lambda cid: (
        [{"service": "ec2", "metric_name": "cpu_utilization_percent",
          "operator": "gt", "threshold_value": 85, "severity": "high",
          "enabled": False}]  # disabled
        if cid == "DEFAULT" else []
    )
    db_service.get_alerts.return_value = []
    ts_service.get_resources_by_service.return_value = [
        {"resource_id": "i-abc", "metric_name": "cpu_utilization_percent", "value": "99.0"}
    ]

    count = await evaluate_thresholds_for_customer(
        "TT-0001", ts_service, db_service, notif_service
    )

    assert count == 0
