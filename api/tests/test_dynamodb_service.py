"""Unit tests for DynamoDBService."""
import hashlib
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from services.dynamodb import DynamoDBService


@pytest.fixture
def db_service():
    with patch("services.dynamodb.boto3") as mock_boto3:
        mock_resource = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        mock_customers = MagicMock()
        mock_alerts = MagicMock()
        mock_thresholds = MagicMock()

        mock_resource.Table.side_effect = lambda name: {
            "tek_watch_customers": mock_customers,
            "tek_watch_alerts": mock_alerts,
            "tek_watch_thresholds": mock_thresholds,
        }.get(name, MagicMock())

        with patch("services.dynamodb.load_config") as mock_config:
            mock_config.return_value = MagicMock(
                aws_region="eu-west-2",
                dynamodb_customers_table="tek_watch_customers",
                dynamodb_alerts_table="tek_watch_alerts",
                dynamodb_thresholds_table="tek_watch_thresholds",
            )
            svc = DynamoDBService()
            svc._customers = mock_customers
            svc._alerts = mock_alerts
            svc._thresholds = mock_thresholds
            return svc, mock_customers, mock_alerts, mock_thresholds


class TestDynamoDBServiceCustomers:
    def test_get_customer_returns_item(self, db_service):
        svc, customers, _, _ = db_service
        customers.get_item.return_value = {
            "Item": {"customer_id": "TT-0001", "SK": "PROFILE", "name": "Acme"}
        }
        result = svc.get_customer("TT-0001")
        assert result["customer_id"] == "TT-0001"
        customers.get_item.assert_called_once_with(
            Key={"customer_id": "TT-0001", "SK": "PROFILE"}
        )

    def test_get_customer_not_found_returns_none(self, db_service):
        svc, customers, _, _ = db_service
        customers.get_item.return_value = {}
        result = svc.get_customer("TT-9999")
        assert result is None

    def test_create_customer_generates_tt_id(self, db_service):
        svc, customers, _, _ = db_service
        customers.scan.return_value = {"Items": []}
        customers.put_item.return_value = {}
        result = svc.create_customer("Acme", "admin@acme.com", "foundation", [])
        assert result["customer_id"] == "TT-0001"
        assert "api_key" in result
        assert len(result["api_key"]) > 20

    def test_create_customer_increments_id(self, db_service):
        svc, customers, _, _ = db_service
        customers.scan.return_value = {
            "Items": [{"customer_id": "TT-0003", "SK": "PROFILE"}]
        }
        customers.put_item.return_value = {}
        result = svc.create_customer("Beta", "b@b.com", "growth", [])
        assert result["customer_id"] == "TT-0004"

    def test_create_customer_api_key_is_hashed(self, db_service):
        svc, customers, _, _ = db_service
        customers.scan.return_value = {"Items": []}
        customers.put_item.return_value = {}
        result = svc.create_customer("Acme", "a@a.com", "foundation", [])
        api_key = result["api_key"]
        stored_hash = result["profile"]["api_key_hash"]
        assert stored_hash == hashlib.sha256(api_key.encode()).hexdigest()

    def test_rotate_api_key_returns_new_key(self, db_service):
        svc, customers, _, _ = db_service
        customers.update_item.return_value = {}
        new_key = svc.rotate_api_key("TT-0001")
        assert new_key is not None
        assert len(new_key) > 20

    def test_update_customer_filters_unsafe_fields(self, db_service):
        svc, customers, _, _ = db_service
        customers.update_item.return_value = {}
        # api_key_hash should not be updatable via update_customer
        result = svc.update_customer("TT-0001", {
            "name": "New Name",
            "api_key_hash": "hacked",  # should be filtered out
        })
        assert result is True
        call_expr = customers.update_item.call_args[1]["UpdateExpression"]
        assert "api_key_hash" not in call_expr


class TestDynamoDBServiceAlerts:
    def test_get_alerts_returns_list(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.query.return_value = {
            "Items": [
                {"customer_id": "TT-0001", "SK": "alert-1", "status": "active"},
                {"customer_id": "TT-0001", "SK": "alert-2", "status": "acknowledged"},
            ]
        }
        result = svc.get_alerts("TT-0001")
        assert len(result) == 2

    def test_get_alerts_filters_by_status(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.query.return_value = {
            "Items": [
                {"customer_id": "TT-0001", "SK": "a1", "status": "active"},
                {"customer_id": "TT-0001", "SK": "a2", "status": "acknowledged"},
            ]
        }
        result = svc.get_alerts("TT-0001", status_filter="active")
        assert len(result) == 1
        assert result[0]["status"] == "active"

    def test_acknowledge_alert_updates_status(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.update_item.return_value = {}
        result = svc.acknowledge_alert("TT-0001", "alert-123")
        assert result is True
        call_kwargs = alerts.update_item.call_args[1]
        assert call_kwargs["Key"] == {"customer_id": "TT-0001", "SK": "alert-123"}


class TestDynamoDBServiceThresholds:
    def test_get_thresholds_default(self, db_service):
        svc, _, _, thresholds = db_service
        thresholds.query.return_value = {
            "Items": [
                {"PK": "DEFAULT", "SK": "ec2#cpu_utilization_percent",
                 "threshold_value": 85, "operator": "gt"}
            ]
        }
        result = svc.get_thresholds("DEFAULT")
        assert len(result) == 1
        assert result[0]["SK"] == "ec2#cpu_utilization_percent"

    def test_upsert_threshold_calls_put_item(self, db_service):
        svc, _, _, thresholds = db_service
        thresholds.put_item.return_value = {}
        result = svc.upsert_threshold(
            "DEFAULT", "ec2", "cpu_utilization_percent",
            {"operator": "gt", "threshold_value": 85, "severity": "high", "enabled": True}
        )
        assert result is True
        thresholds.put_item.assert_called_once()


class TestCreateAlertDedupe:
    """create_alert's dedupe_key closes a read-then-write race.

    Callers read "is there an active alert for this resource?" and then write.
    With api_desired_count above 1 (the default in variables.tf) two replicas
    can both read "no" and both write, producing duplicate alerts and duplicate
    notifications. dedupe_key makes the range key deterministic and the write
    conditional so DynamoDB settles it atomically.
    """

    def test_dedupe_key_makes_the_range_key_deterministic(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.put_item.return_value = {}
        alert_id = svc.create_alert(
            "TT-0001", {"type": "threshold"}, dedupe_key="ec2#i-123#cpu"
        )
        assert alert_id == "THRESHOLD#ec2#i-123#cpu"
        item = alerts.put_item.call_args.kwargs["Item"]
        assert item["SK"] == "THRESHOLD#ec2#i-123#cpu"

    def test_dedupe_key_writes_conditionally(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.put_item.return_value = {}
        svc.create_alert("TT-0001", {"type": "threshold"}, dedupe_key="ec2#i-123#cpu")
        kwargs = alerts.put_item.call_args.kwargs
        # Allows a fresh alert once the previous one is resolved; a plain
        # attribute_not_exists would block that forever.
        assert kwargs["ConditionExpression"] == "attribute_not_exists(SK) OR #st <> :active"
        assert kwargs["ExpressionAttributeValues"] == {":active": "active"}

    def test_losing_the_race_returns_empty_not_an_error(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
            "PutItem",
        )
        # "" tells the caller not to send a duplicate notification.
        assert svc.create_alert("TT-0001", {}, dedupe_key="ec2#i-123#cpu") == ""

    def test_without_dedupe_key_writes_unconditionally(self, db_service):
        svc, _, alerts, _ = db_service
        alerts.put_item.return_value = {}
        alert_id = svc.create_alert("TT-0001", {"type": "manual"})
        assert not alert_id.startswith("THRESHOLD#")
        assert "ConditionExpression" not in alerts.put_item.call_args.kwargs
