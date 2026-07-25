"""Integration tests for API endpoints using FastAPI TestClient."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mock_customer_context():
    """Mock CustomerContext returned by get_current_customer dependency."""
    from auth.dependencies import CustomerContext
    return CustomerContext(
        customer_id="TT-0001",
        cognito_sub="sub-abc-123",
        email="test@acme.com",
    )


@pytest.fixture(scope="module")
def client(mock_customer_context):
    """Create TestClient with mocked auth and services."""
    with patch("auth.cognito._get_jwks"), \
         patch("services.timestream.boto3"), \
         patch("services.dynamodb.boto3"), \
         patch("services.notifications.boto3"), \
         patch("services.timestream.load_config") as mock_ts_cfg, \
         patch("services.dynamodb.load_config") as mock_db_cfg, \
         patch("services.notifications.load_config") as mock_notif_cfg, \
         patch("config.load_config") as mock_cfg:

        cfg = MagicMock(
            aws_region="eu-west-2",
            environment="test",
            log_level="INFO",
            dynamodb_metrics_table="tek_watch_metrics",
            dynamodb_events_table="tek_watch_events",
            dynamodb_customers_table="tek_watch_customers",
            dynamodb_alerts_table="tek_watch_alerts",
            dynamodb_thresholds_table="tek_watch_thresholds",
            cognito_customer_user_pool_id="eu-west-2_TEST",
            cognito_customer_app_client_id="test-client",
            cognito_admin_user_pool_id="eu-west-2_ADMIN",
            cognito_admin_app_client_id="admin-client",
            anthropic_api_key="",
            sns_ops_alerts_topic_arn="",
            sqs_ingest_queue_url="",
        )
        mock_cfg.return_value = cfg
        mock_ts_cfg.return_value = cfg
        mock_db_cfg.return_value = cfg
        mock_notif_cfg.return_value = cfg

        from main import create_app
        from auth.dependencies import get_current_customer

        app = create_app()
        app.dependency_overrides[get_current_customer] = lambda: mock_customer_context

        yield TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestOverviewEndpoint:
    def test_overview_requires_auth(self):
        """Without dependency override, should return 401."""
        with patch("config.load_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(
                environment="test", log_level="INFO",
                cognito_customer_user_pool_id="eu-west-2_TEST",
                cognito_customer_app_client_id="test-client",
                cognito_admin_user_pool_id="eu-west-2_ADMIN",
                cognito_admin_app_client_id="admin-client",
                anthropic_api_key="", sns_ops_alerts_topic_arn="",
                sqs_ingest_queue_url="",
                dynamodb_metrics_table="tek_watch_metrics",
                dynamodb_events_table="tek_watch_events",
                dynamodb_customers_table="tek_watch_customers",
                dynamodb_alerts_table="tek_watch_alerts",
                dynamodb_thresholds_table="tek_watch_thresholds",
                aws_region="eu-west-2",
            )
            from main import create_app
            app = create_app()
            c = TestClient(app, raise_server_exceptions=False)
            resp = c.get("/api/v1/overview")
            assert resp.status_code == 403  # No auth header

    def test_overview_returns_expected_shape(self, client):
        with patch("routers.overview.TimestreamQueryService") as mock_ts, \
             patch("routers.overview.DynamoDBService") as mock_db:
            mock_ts.return_value.get_latest_metric.return_value = 1250.0
            mock_ts.return_value.get_resources_by_service.return_value = []
            mock_db.return_value.get_customer.return_value = {
                "agent_status": "healthy",
                "last_agent_seen": "2026-01-01T00:00:00+00:00",
            }
            mock_db.return_value.get_alerts.return_value = []

            resp = client.get("/api/v1/overview")
            assert resp.status_code == 200
            data = resp.json()
            assert "total_resources" in data
            assert "active_alarms" in data
            assert "agent_status" in data
            assert "estimated_monthly_cost" in data


class TestAlertsEndpoint:
    def test_get_alerts_returns_list(self, client):
        with patch("routers.alerts.DynamoDBService") as mock_db:
            mock_db.return_value.get_alerts.return_value = [
                {
                    "alert_id": "alert-1",
                    "type": "threshold",
                    "severity": "high",
                    "service": "ec2",
                    "resource_id": "i-abc",
                    "metric_name": "cpu_utilization_percent",
                    "description": "CPU > 85%",
                    "status": "active",
                    "triggered_at": "2026-01-01T00:00:00+00:00",
                }
            ]
            resp = client.get("/api/v1/alerts")
            assert resp.status_code == 200
            assert "alerts" in resp.json()
            assert len(resp.json()["alerts"]) == 1

    def test_acknowledge_alert_returns_200(self, client):
        with patch("routers.alerts.DynamoDBService") as mock_db:
            mock_db.return_value.acknowledge_alert.return_value = True
            resp = client.put("/api/v1/alerts/alert-123/acknowledge")
            assert resp.status_code == 200
            assert resp.json()["status"] == "acknowledged"

    def test_acknowledge_nonexistent_alert_returns_404(self, client):
        with patch("routers.alerts.DynamoDBService") as mock_db:
            mock_db.return_value.acknowledge_alert.return_value = False
            resp = client.put("/api/v1/alerts/nonexistent/acknowledge")
            assert resp.status_code == 404


class TestComputeEndpoints:
    def test_ec2_endpoint_returns_instances(self, client):
        with patch("routers.compute.TimestreamQueryService") as mock_ts:
            mock_ts.return_value.get_resources_by_service.return_value = [
                {"resource_id": "i-abc", "resource_name": "web", "metric_name": "instance_state",
                 "value": "running", "time": "2026-01-01T00:00:00Z"}
            ]
            resp = client.get("/api/v1/compute/ec2")
            assert resp.status_code == 200
            assert "instances" in resp.json()

    def test_lambda_endpoint_returns_functions(self, client):
        with patch("routers.compute.TimestreamQueryService") as mock_ts:
            mock_ts.return_value.get_resources_by_service.return_value = []
            resp = client.get("/api/v1/compute/lambda")
            assert resp.status_code == 200
            assert "functions" in resp.json()


class TestMetricsEndpoint:
    def test_metrics_endpoint_returns_time_series(self, client):
        with patch("routers.metrics.TimestreamQueryService") as mock_ts:
            mock_ts.return_value.get_time_series.return_value = [
                {"time": "2026-01-01T00:00:00Z", "value": "73.4"}
            ]
            resp = client.get(
                "/api/v1/metrics/i-abc123",
                params={"metric_name": "cpu_utilization_percent", "time_range": "24h"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["resource_id"] == "i-abc123"
            assert data["metric_name"] == "cpu_utilization_percent"
            assert "data" in data


class TestAgentCfnTemplateEndpoint:
    def test_returns_yaml_attachment_for_own_customer(self, client):
        with patch("routers.agent.DynamoDBService") as mock_db:
            mock_db.return_value.get_customer.return_value = {
                "customer_id": "TT-0001", "name": "Acme Ltd",
            }
            resp = client.get("/api/v1/agent/cfn-template")
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("application/x-yaml")
            assert "attachment" in resp.headers["content-disposition"]
            assert "TT-0001" in resp.text
            assert "AgentTaskRole" in resp.text

    def test_404_when_profile_missing(self, client):
        with patch("routers.agent.DynamoDBService") as mock_db:
            mock_db.return_value.get_customer.return_value = None
            resp = client.get("/api/v1/agent/cfn-template")
            assert resp.status_code == 404
