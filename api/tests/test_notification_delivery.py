"""Customer alert delivery: preferences, severity gating, Slack URL safety."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.notifications import NotificationPreferences, update_preferences
from services.alerting.threshold import evaluate_thresholds_for_customer
from services.notifications import NotificationService, is_slack_webhook

SLACK = "https://hooks.slack.com/services/T000/B000/XXXX"


def service():
    """A NotificationService with no AWS clients and its senders mocked."""
    svc = NotificationService.__new__(NotificationService)
    svc.send_alert_email = AsyncMock()
    svc.send_slack_alert = AsyncMock()
    return svc


def customer(**prefs):
    return {"customer_id": "TT-1", "email": "owner@example.co.uk", "notification_preferences": prefs}


async def deliver(svc, cust, severity="high"):
    await svc.deliver_to_customer(
        cust, service="ec2", resource_id="i-1", metric_name="cpu", severity=severity, current_value=97.0,
    )


class TestSlackUrl:
    @pytest.mark.parametrize("url", [SLACK])
    def test_accepts_slack_webhooks(self, url):
        assert is_slack_webhook(url)

    @pytest.mark.parametrize("url", [
        "http://hooks.slack.com/services/T/B/X",          # not https
        "http://169.254.169.254/latest/meta-data/",       # instance metadata
        "https://hooks.slack.com.evil.example/services/x",
        "https://evil.example/?https://hooks.slack.com/services/",
        "https://internal.local/hook",
        "",
        None,
    ])
    def test_rejects_everything_else(self, url):
        assert not is_slack_webhook(url)


@pytest.mark.asyncio
class TestDeliverToCustomer:
    async def test_email_and_slack_both_sent(self):
        svc = service()
        await deliver(svc, customer(email_address="alerts@example.co.uk", slack_webhook_url=SLACK))
        assert svc.send_alert_email.await_args.kwargs["to_address"] == "alerts@example.co.uk"
        assert svc.send_slack_alert.await_args.kwargs["webhook_url"] == SLACK

    async def test_falls_back_to_account_email(self):
        svc = service()
        await deliver(svc, customer())
        assert svc.send_alert_email.await_args.kwargs["to_address"] == "owner@example.co.uk"

    async def test_email_disabled(self):
        svc = service()
        await deliver(svc, customer(email_enabled=False))
        svc.send_alert_email.assert_not_awaited()

    async def test_below_minimum_severity_is_not_sent(self):
        svc = service()
        await deliver(svc, customer(min_severity="critical", slack_webhook_url=SLACK), severity="high")
        svc.send_alert_email.assert_not_awaited()
        svc.send_slack_alert.assert_not_awaited()

    async def test_medium_meets_warning_minimum(self):
        svc = service()
        await deliver(svc, customer(min_severity="warning"), severity="medium")
        svc.send_alert_email.assert_awaited_once()

    async def test_low_below_default_minimum(self):
        svc = service()
        await deliver(svc, customer(), severity="low")
        svc.send_alert_email.assert_not_awaited()

    async def test_stored_non_slack_webhook_is_never_called(self):
        svc = service()
        await deliver(svc, customer(slack_webhook_url="http://169.254.169.254/latest/"))
        svc.send_slack_alert.assert_not_awaited()


@pytest.mark.asyncio
class TestPreferencesRouter:
    async def test_rejects_non_slack_webhook(self):
        prefs = NotificationPreferences(slack_webhook_url="http://169.254.169.254/latest/")
        with pytest.raises(HTTPException) as exc:
            await update_preferences(prefs, customer=MagicMock(customer_id="TT-1"))
        assert exc.value.status_code == 422

    async def test_accepts_slack_webhook(self):
        prefs = NotificationPreferences(slack_webhook_url=SLACK)
        with patch("routers.notifications.DynamoDBService") as db:
            result = await update_preferences(prefs, customer=MagicMock(customer_id="TT-1"))
        assert result["status"] == "updated"
        db.return_value.update_customer.assert_called_once()


@pytest.mark.asyncio
async def test_threshold_alert_reaches_the_customer():
    ts = MagicMock()
    ts.get_latest_numeric_metrics.return_value = [
        {"resource_id": "i-1", "resource_name": "web", "metric_name": "cpu_utilization_percent", "value": 97},
    ]
    db = MagicMock()
    db.get_thresholds.side_effect = lambda cid: (
        [{"service": "ec2", "metric_name": "cpu_utilization_percent", "operator": "gt",
          "threshold_value": 85, "severity": "high", "enabled": True}]
        if cid == "DEFAULT" else []
    )
    db.get_alerts.return_value = []
    db.create_alert.return_value = "alert-1"
    db.get_customer.return_value = customer()
    notif = MagicMock()
    notif.send_ops_alert = AsyncMock()
    notif.deliver_to_customer = AsyncMock()

    assert await evaluate_thresholds_for_customer("TT-1", ts, db, notif) == 1
    notif.deliver_to_customer.assert_awaited_once()
    assert notif.deliver_to_customer.await_args.args[0]["customer_id"] == "TT-1"
    assert notif.deliver_to_customer.await_args.kwargs["severity"] == "high"


@pytest.mark.asyncio
async def test_delivery_failure_does_not_stop_evaluation():
    ts = MagicMock()
    ts.get_latest_numeric_metrics.return_value = [
        {"resource_id": "i-1", "metric_name": "cpu_utilization_percent", "value": 97},
        {"resource_id": "i-2", "metric_name": "cpu_utilization_percent", "value": 99},
    ]
    db = MagicMock()
    db.get_thresholds.side_effect = lambda cid: (
        [{"service": "ec2", "metric_name": "cpu_utilization_percent", "operator": "gt",
          "threshold_value": 85, "severity": "high"}]
        if cid == "DEFAULT" else []
    )
    db.get_alerts.return_value = []
    db.create_alert.side_effect = ["a1", "a2"]
    db.get_customer.return_value = customer()
    notif = MagicMock()
    notif.send_ops_alert = AsyncMock()
    notif.deliver_to_customer = AsyncMock(side_effect=RuntimeError("SES down"))

    assert await evaluate_thresholds_for_customer("TT-1", ts, db, notif) == 2
    db.get_customer.assert_called_once()   # fetched once, not per alert
