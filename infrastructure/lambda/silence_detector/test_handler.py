"""Unit tests for the silence detector Lambda."""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError

import handler as h


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _iso(delta_minutes: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=delta_minutes)).isoformat()


def _client_error(code: str = "ConditionalCheckFailedException") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "op")


# ─── is_silent ────────────────────────────────────────────────────────────────

class TestIsSilent:
    def test_recent_heartbeat_is_not_silent(self):
        assert h.is_silent(_iso(5), threshold_minutes=20) is False

    def test_old_heartbeat_is_silent(self):
        assert h.is_silent(_iso(25), threshold_minutes=20) is True

    def test_well_within_threshold_is_not_silent(self):
        assert h.is_silent(_iso(10), threshold_minutes=20) is False

    def test_unparseable_timestamp_is_silent(self):
        assert h.is_silent("not-a-date", threshold_minutes=20) is True

    def test_none_timestamp_is_silent(self):
        assert h.is_silent(None, threshold_minutes=20) is True

    def test_z_suffix_is_handled(self):
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        assert h.is_silent(ts, threshold_minutes=20) is False


# ─── build_alert ──────────────────────────────────────────────────────────────

class TestBuildAlert:
    def test_returns_critical_alert(self):
        alert = h.build_alert("TT-0001", _iso(25), 25.0)
        assert alert["severity"] == "critical"
        assert alert["status"] == "active"
        assert alert["type"] == "agent_silence"
        assert alert["customer_id"] == "TT-0001"

    def test_alert_id_is_deterministic(self):
        alert = h.build_alert("TT-0042", _iso(30), 30.0)
        assert alert["alert_id"] == "SILENCE-TT-0042"

    def test_threshold_value_matches_env(self):
        alert = h.build_alert("TT-0001", _iso(25), 25.0)
        assert alert["threshold_value"] == float(h.SILENCE_MIN)

    def test_description_mentions_gap(self):
        alert = h.build_alert("TT-0001", _iso(30), 30.0)
        assert "30" in alert["description"]

    def test_recommendation_is_non_empty(self):
        alert = h.build_alert("TT-0001", _iso(25), 25.0)
        assert len(alert["recommendation"]) > 20


# ─── upsert_alert ─────────────────────────────────────────────────────────────

class TestUpsertAlert:
    def test_calls_put_item(self):
        ddb   = MagicMock()
        table = MagicMock()
        ddb.Table.return_value = table
        alert = {"alert_id": "SILENCE-TT-0001", "customer_id": "TT-0001"}
        h.upsert_alert(ddb, alert)
        table.put_item.assert_called_once_with(Item=alert)

    def test_handles_client_error_gracefully(self):
        ddb   = MagicMock()
        table = MagicMock()
        ddb.Table.return_value = table
        table.put_item.side_effect = _client_error("ProvisionedThroughputExceededException")
        h.upsert_alert(ddb, {"alert_id": "X", "customer_id": "Y"})   # must not raise


# ─── resolve_alert ─────────────────────────────────────────────────────────────

class TestResolveAlert:
    def test_calls_update_item(self):
        ddb   = MagicMock()
        table = MagicMock()
        ddb.Table.return_value = table
        table.update_item.return_value = {}
        h.resolve_alert(ddb, "TT-0001")
        assert table.update_item.called

    def test_handles_condition_check_failed(self):
        ddb   = MagicMock()
        table = MagicMock()
        ddb.Table.return_value = table
        exc = _client_error("ConditionalCheckFailedException")
        table.update_item.side_effect = exc
        # Simulate the conditional check behaviour expected by the handler
        ddb.meta.client.exceptions.ConditionalCheckFailedException = type(exc)
        h.resolve_alert(ddb, "TT-0001")   # must not raise


# ─── handler (integration-style) ──────────────────────────────────────────────

class TestHandler:
    def _make_ddb(self, customers: list) -> MagicMock:
        ddb   = MagicMock()
        table = MagicMock()
        ddb.Table.return_value = table
        table.scan.return_value = {"Items": customers}
        table.update_item.return_value = {}
        table.put_item.return_value    = {}
        ddb.meta.client.exceptions.ConditionalCheckFailedException = Exception
        return ddb

    def test_silent_customer_triggers_alert(self):
        customers = [{"customer_id": "TT-0001", "last_heartbeat": _iso(30)}]
        ddb = self._make_ddb(customers)
        with patch.object(h, "_get_dynamodb", return_value=ddb):
            with patch.object(h, "notify_operator") as mock_notify:
                result = h.handler({}, None)
        assert result["silenced"] == 1
        assert result["resolved"] == 0
        mock_notify.assert_called_once()

    def test_active_customer_resolves_alert(self):
        customers = [{"customer_id": "TT-0001", "last_heartbeat": _iso(5)}]
        ddb = self._make_ddb(customers)
        with patch.object(h, "_get_dynamodb", return_value=ddb):
            result = h.handler({}, None)
        assert result["silenced"] == 0
        assert result["resolved"] == 1

    def test_checked_count_matches_customers(self):
        customers = [
            {"customer_id": "TT-0001", "last_heartbeat": _iso(5)},
            {"customer_id": "TT-0002", "last_heartbeat": _iso(30)},
            {"customer_id": "TT-0003", "last_heartbeat": _iso(10)},
        ]
        ddb = self._make_ddb(customers)
        with patch.object(h, "_get_dynamodb", return_value=ddb):
            with patch.object(h, "notify_operator"):
                result = h.handler({}, None)
        assert result["checked"] == 3
        assert result["silenced"] == 1
        assert result["resolved"] == 2

    def test_missing_heartbeat_skipped(self):
        customers = [{"customer_id": "TT-0001"}]   # no last_heartbeat key
        ddb = self._make_ddb(customers)
        with patch.object(h, "_get_dynamodb", return_value=ddb):
            result = h.handler({}, None)
        assert result["checked"] == 1
        assert result["silenced"] == 0
        assert result["resolved"] == 0

    def test_empty_customer_list_returns_zeroes(self):
        ddb = self._make_ddb([])
        with patch.object(h, "_get_dynamodb", return_value=ddb):
            result = h.handler({}, None)
        assert result == {"checked": 0, "silenced": 0, "resolved": 0}
