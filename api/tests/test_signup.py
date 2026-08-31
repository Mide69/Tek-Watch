"""Tests for the public self-service signup endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

import auth.cognito  # noqa: F401, ensures the submodule is patchable in isolation
import routers.signup  # noqa: F401, same reason


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The signup endpoint is rate-limited (5/minute); the limiter is a
    process-wide singleton, so without a reset the 6th+ test in this file
    would start getting 429s regardless of what it's actually testing."""
    from rate_limit import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    """TestClient with a fully mocked config (real Cognito pool configured)."""
    with patch("auth.cognito._get_jwks"), \
         patch("services.dynamodb.boto3"), \
         patch("services.notifications.boto3"), \
         patch("services.cognito_admin.boto3"), \
         patch("services.dynamodb.load_config") as mock_db_cfg, \
         patch("services.notifications.load_config") as mock_notif_cfg, \
         patch("routers.signup.load_config") as mock_signup_cfg, \
         patch("config.load_config") as mock_cfg:

        cfg = MagicMock(
            aws_region="eu-west-2",
            environment="test",
            log_level="INFO",
            dynamodb_customers_table="tek_watch_customers",
            cognito_customer_user_pool_id="eu-west-2_TEST",
            cognito_customer_app_client_id="test-client",
            cognito_admin_user_pool_id="eu-west-2_ADMIN",
            cognito_admin_app_client_id="admin-client",
            ses_from_email="hello@tekwatch.co.uk",
            sqs_ingest_queue_url="",
        )
        mock_cfg.return_value = cfg
        mock_db_cfg.return_value = cfg
        mock_notif_cfg.return_value = cfg
        mock_signup_cfg.return_value = cfg

        from main import create_app

        app = create_app()
        yield TestClient(app)


@pytest.fixture
def client_no_cognito():
    """TestClient with no Cognito pool configured (dev-mode fallback path)."""
    with patch("auth.cognito._get_jwks"), \
         patch("services.dynamodb.boto3"), \
         patch("services.notifications.boto3"), \
         patch("services.cognito_admin.boto3"), \
         patch("services.dynamodb.load_config") as mock_db_cfg, \
         patch("routers.signup.load_config") as mock_signup_cfg, \
         patch("config.load_config") as mock_cfg:

        cfg = MagicMock(
            aws_region="eu-west-2",
            environment="test",
            dynamodb_customers_table="tek_watch_customers",
            cognito_customer_user_pool_id="",
            ses_from_email="",
            sqs_ingest_queue_url="",
        )
        mock_cfg.return_value = cfg
        mock_db_cfg.return_value = cfg
        mock_signup_cfg.return_value = cfg

        from main import create_app

        app = create_app()
        yield TestClient(app)


VALID_BODY = {"name": "Jane Smith", "email": "jane@acme.co.uk", "company": "Acme Ltd"}


class TestSignup:
    def test_successful_signup_creates_login_and_emails_it(self, client):
        with patch("routers.signup.DynamoDBService") as mock_db, \
             patch("routers.signup.provision_customer_login") as mock_provision, \
             patch("routers.signup.NotificationService") as mock_notif:
            mock_db.return_value.list_customers.return_value = []
            mock_db.return_value.create_customer.return_value = {
                "customer_id": "TT-0002", "api_key": "unused-here", "profile": {},
            }
            mock_notif.return_value.send_customer_email = AsyncMock()

            resp = client.post("/api/v1/signup", json=VALID_BODY)

            assert resp.status_code == 201
            data = resp.json()
            assert data["customer_id"] == "TT-0002"
            # The generated password must never reach the API response. Asserts
            # the VALUE is absent, not the word: the response now tells the user
            # a temporary password was emailed, which is wording, not a leak.
            sent_password = mock_provision.call_args.kwargs["password"]
            assert sent_password not in resp.text

            mock_provision.assert_called_once()
            assert mock_provision.call_args.kwargs["customer_id"] == "TT-0002"
            assert mock_provision.call_args.kwargs["email"] == "jane@acme.co.uk"
            mock_notif.return_value.send_customer_email.assert_called_once()

    def test_duplicate_email_is_rejected(self, client):
        with patch("routers.signup.DynamoDBService") as mock_db:
            mock_db.return_value.list_customers.return_value = [
                {"customer_id": "TT-0001", "email": "jane@acme.co.uk"}
            ]
            resp = client.post("/api/v1/signup", json=VALID_BODY)
            assert resp.status_code == 409

    def test_duplicate_email_check_is_case_insensitive(self, client):
        with patch("routers.signup.DynamoDBService") as mock_db:
            mock_db.return_value.list_customers.return_value = [
                {"customer_id": "TT-0001", "email": "JANE@ACME.CO.UK"}
            ]
            resp = client.post("/api/v1/signup", json=VALID_BODY)
            assert resp.status_code == 409

    def test_cognito_failure_rolls_back_customer_record(self, client):
        with patch("routers.signup.DynamoDBService") as mock_db, \
             patch("routers.signup.provision_customer_login") as mock_provision:
            mock_db.return_value.list_customers.return_value = []
            mock_db.return_value.create_customer.return_value = {
                "customer_id": "TT-0003", "api_key": "x", "profile": {},
            }
            mock_provision.side_effect = ClientError(
                {"Error": {"Code": "InternalError", "Message": "boom"}}, "AdminCreateUser"
            )

            resp = client.post("/api/v1/signup", json=VALID_BODY)

            assert resp.status_code == 503
            mock_db.return_value.delete_customer.assert_called_once_with("TT-0003")

    def test_invalid_email_is_rejected(self, client):
        resp = client.post("/api/v1/signup", json={**VALID_BODY, "email": "not-an-email"})
        assert resp.status_code == 422

    def test_missing_name_is_rejected(self, client):
        resp = client.post("/api/v1/signup", json={"email": "jane@acme.co.uk"})
        assert resp.status_code == 422

    def test_dev_mode_without_cognito_pool_skips_provisioning(self, client_no_cognito):
        with patch("routers.signup.DynamoDBService") as mock_db, \
             patch("routers.signup.provision_customer_login") as mock_provision:
            mock_db.return_value.list_customers.return_value = []
            mock_db.return_value.create_customer.return_value = {
                "customer_id": "TT-0004", "api_key": "x", "profile": {},
            }

            resp = client_no_cognito.post("/api/v1/signup", json=VALID_BODY)

            assert resp.status_code == 201
            mock_provision.assert_not_called()


class TestSignupEmailDelivery:
    """Cognito must be the one emailing the credentials.

    The app previously suppressed Cognito's invite and sent its own SES email
    instead. SES was never configured, and send_customer_email returns silently
    when it isn't — so signup reported success having delivered nothing, leaving
    the customer with an account they could not learn about.

    Asserts the call boto3 actually receives, not the source text: an earlier
    version of this test grepped for "SUPPRESS" and failed on the comment
    explaining why it was removed.
    """

    def _provision(self):
        from unittest.mock import patch, MagicMock
        from services.cognito_admin import provision_customer_login
        with patch("services.cognito_admin.boto3") as mock_boto3:
            client = MagicMock()
            mock_boto3.client.return_value = client
            provision_customer_login(
                user_pool_id="eu-west-2_test",
                region="eu-west-2",
                customer_id="TT-0009",
                email="new@example.com",
                password="Sup3rSecret!",
            )
            return client

    def test_cognito_sends_the_invite_email(self):
        client = self._provision()
        kwargs = client.admin_create_user.call_args.kwargs
        assert kwargs.get("MessageAction") != "SUPPRESS"
        assert kwargs.get("DesiredDeliveryMediums") == ["EMAIL"]

    def test_no_permanent_password_is_set(self):
        # The customer lands in FORCE_CHANGE_PASSWORD and chooses their own, so
        # no password we generated is ever a working credential.
        client = self._provision()
        client.admin_set_user_password.assert_not_called()
