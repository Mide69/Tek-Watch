"""Unit tests for the IAMCollector."""
import csv
import io
import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.iam import IAMCollector


def make_credential_report(rows: list[dict]) -> bytes:
    """Build a fake IAM credential report CSV."""
    fieldnames = [
        "user", "password_enabled", "mfa_active",
        "access_key_1_active", "access_key_1_last_rotated",
        "access_key_2_active", "access_key_2_last_rotated",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({f: row.get(f, "false") for f in fieldnames})
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def collector():
    session = MagicMock()
    iam = MagicMock()
    session.client.return_value = iam
    c = IAMCollector(session, "global", "TT-0001")
    c._iam = iam
    return c, iam


def _setup_credential_report(iam, rows):
    report_bytes = make_credential_report(rows)
    iam.generate_credential_report.return_value = {"State": "COMPLETE"}
    iam.get_credential_report.return_value = {"Content": report_bytes}


class TestIAMCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "iam"

    def test_region_is_always_global(self, collector):
        c, _ = collector
        assert c.region == "global"

    def test_root_mfa_active_emitted(self, collector):
        c, iam = collector
        _setup_credential_report(iam, [
            {"user": "<root_account>", "mfa_active": "true"},
        ])
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 0, "Roles": 0}}

        records = c.collect()
        root_mfa = next(r for r in records if r.metric_name == "root_mfa_active")
        assert root_mfa.metric_value == "true"

    def test_users_without_mfa_counted(self, collector):
        c, iam = collector
        _setup_credential_report(iam, [
            {"user": "alice", "password_enabled": "true", "mfa_active": "false"},
            {"user": "bob",   "password_enabled": "true", "mfa_active": "true"},
            {"user": "carol", "password_enabled": "true", "mfa_active": "false"},
        ])
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 3, "Roles": 0}}

        records = c.collect()
        mfa_rec = next(r for r in records if r.metric_name == "users_without_mfa_count")
        assert mfa_rec.metric_value == 2

    def test_old_access_keys_counted(self, collector):
        c, iam = collector
        _setup_credential_report(iam, [
            {
                "user": "dev-user",
                "password_enabled": "true",
                "mfa_active": "true",
                "access_key_1_active": "true",
                "access_key_1_last_rotated": "2024-01-01T00:00:00+00:00",  # > 90 days old
            },
        ])
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 1, "Roles": 0}}

        records = c.collect()
        old_keys = next(r for r in records if r.metric_name == "access_keys_older_than_90_days")
        assert old_keys.metric_value == 1

    def test_recently_rotated_key_not_counted(self, collector):
        c, iam = collector
        _setup_credential_report(iam, [
            {
                "user": "dev-user",
                "password_enabled": "true",
                "mfa_active": "true",
                "access_key_1_active": "true",
                "access_key_1_last_rotated": "2026-05-01T00:00:00+00:00",  # recent
            },
        ])
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 1, "Roles": 0}}

        records = c.collect()
        old_keys = next(r for r in records if r.metric_name == "access_keys_older_than_90_days")
        assert old_keys.metric_value == 0

    def test_account_summary_user_and_role_counts(self, collector):
        c, iam = collector
        _setup_credential_report(iam, [])
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 10, "Roles": 25}}

        records = c.collect()
        users = next(r for r in records if r.metric_name == "total_users")
        roles = next(r for r in records if r.metric_name == "total_roles")
        assert users.metric_value == 10
        assert roles.metric_value == 25

    def test_credential_report_denied_skips_report_records(self, collector):
        c, iam = collector
        iam.generate_credential_report.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "GenerateCredentialReport",
        )
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 0, "Roles": 0}}

        records = c.collect()
        # credential report records absent; account summary records still emitted
        assert not any(r.metric_name == "root_mfa_active" for r in records)
        assert not any(r.metric_name == "users_without_mfa_count" for r in records)
        assert any(r.metric_name == "total_users" for r in records)

    def test_customer_id_propagated(self, collector):
        c, iam = collector
        _setup_credential_report(iam, [])
        iam.get_account_summary.return_value = {"SummaryMap": {"Users": 0, "Roles": 0}}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
