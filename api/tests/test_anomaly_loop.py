"""The anomaly loop: our detector decides, Claude only words it."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.alerting import anomaly
from services.alerting.detector import Anomaly, describe

SPIKE = Anomaly("ec2", "i-1", "cpu_utilization_percent", "spike", "high", 95.0, 40.0, 5.0, 11.0, 2000)
DROP = Anomaly("lambda", "fn", "invocations", "drop", "medium", 1.0, 400.0, 50.0, -7.98, 2000)


def claude_returning(text):
    client = MagicMock()
    client.messages.create.return_value = MagicMock(content=[MagicMock(text=text)])
    return client


@pytest.mark.asyncio
class TestExplain:
    async def test_without_a_key_uses_built_in_wording(self):
        assert await anomaly.explain([SPIKE, DROP], None) == [describe(SPIKE), describe(DROP)]

    async def test_uses_claude_wording_when_one_for_one(self):
        client = claude_returning(json.dumps([
            {"description": "CPU is very high.", "recommendation": "Check the last deploy."},
            {"description": "Calls fell away.", "recommendation": "Check the trigger."},
        ]))
        assert await anomaly.explain([SPIKE, DROP], client) == [
            ("CPU is very high.", "Check the last deploy."),
            ("Calls fell away.", "Check the trigger."),
        ]

    async def test_claude_cannot_add_or_drop_items(self):
        client = claude_returning(json.dumps([{"description": "x", "recommendation": "y"}]))
        assert await anomaly.explain([SPIKE, DROP], client) == [describe(SPIKE), describe(DROP)]

    async def test_malformed_reply_falls_back(self):
        client = claude_returning("Sure! Here are your anomalies:")
        assert await anomaly.explain([SPIKE], client) == [describe(SPIKE)]

    async def test_outage_falls_back(self):
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("overloaded")
        assert await anomaly.explain([SPIKE], client) == [describe(SPIKE)]

    async def test_payload_sent_is_the_detected_anomalies(self):
        client = claude_returning(json.dumps([{"description": "d", "recommendation": "r"}]))
        await anomaly.explain([SPIKE], client)
        sent = json.loads(client.messages.create.call_args.kwargs["messages"][0]["content"])
        assert sent[0]["severity"] == "high" and sent[0]["resource_id"] == "i-1"


def services(active=None):
    now = datetime.now(timezone.utc)
    ts = MagicMock()
    ts.get_7day_summary.return_value = [{
        "service": "ec2", "resource_id": "i-1", "metric_name": "cpu_utilization_percent",
        "avg_value": 40.0, "stddev_value": 5.0, "samples": 2000,
        "first_time": (now - timedelta(days=7)).isoformat(),
    }]
    ts.get_last_hour.return_value = [{
        "service": "ec2", "resource_id": "i-1", "metric_name": "cpu_utilization_percent",
        "value": 95.0, "time": now.isoformat(),
    }]
    db = MagicMock()
    db.get_alerts.return_value = active or []
    db.create_alert.return_value = "alert-1"
    notif = MagicMock()
    notif.send_ops_alert = AsyncMock()
    notif.deliver_to_customer = AsyncMock()
    return ts, db, notif


@pytest.mark.asyncio
class TestDetectForCustomer:
    async def test_runs_with_no_claude_client(self):
        ts, db, notif = services()
        created = await anomaly.detect_anomalies_for_customer(
            "TT-1", ts, db, notif, None, {"customer_id": "TT-1"})
        assert created == 1
        alert = db.create_alert.call_args.args[1]
        assert alert["severity"] == "high"
        assert alert["metric_name"] == "cpu_utilization_percent"
        assert alert["detection"]["method"] == "spike"
        assert (alert["description"], alert["recommendation"]) == describe(SPIKE)
        assert db.create_alert.call_args.kwargs["dedupe_key"] == "anomaly:ec2#i-1#cpu_utilization_percent"

    async def test_delivers_to_the_customer(self):
        ts, db, notif = services()
        await anomaly.detect_anomalies_for_customer("TT-1", ts, db, notif, None, {"customer_id": "TT-1"})
        notif.deliver_to_customer.assert_awaited_once()
        assert notif.deliver_to_customer.await_args.kwargs["severity"] == "high"

    async def test_already_active_is_not_raised_again(self):
        active = [{"type": "ai_anomaly", "service": "ec2", "resource_id": "i-1",
                   "metric_name": "cpu_utilization_percent"}]
        ts, db, notif = services(active)
        assert await anomaly.detect_anomalies_for_customer("TT-1", ts, db, notif, None, {}) == 0
        db.create_alert.assert_not_called()

    async def test_duplicate_from_another_replica_is_not_delivered(self):
        ts, db, notif = services()
        db.create_alert.return_value = ""
        assert await anomaly.detect_anomalies_for_customer("TT-1", ts, db, notif, None, {}) == 0
        notif.deliver_to_customer.assert_not_awaited()

    async def test_numbers_stored_as_decimals(self):
        from decimal import Decimal
        ts, db, notif = services()
        await anomaly.detect_anomalies_for_customer("TT-1", ts, db, notif, None, {})
        alert = db.create_alert.call_args.args[1]
        assert isinstance(alert["current_value"], Decimal)
        assert isinstance(alert["detection"]["z_score"], Decimal)


def test_no_key_means_no_client_not_no_loop():
    with patch("services.alerting.anomaly.load_config", return_value=MagicMock(anthropic_api_key="")):
        assert anomaly._claude_client() is None
