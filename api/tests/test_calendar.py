"""The regulatory calendar: real dates only, and honest about the ones we lack."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from routers import security
from services import calendar

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
CTX = MagicMock(customer_id="TT-1")


def incident(kind="s3_public_exposure", detected=None, resource="customer-exports"):
    return {
        "id": f"{kind}:{resource}",
        "type": kind,
        "detected_at": (detected or NOW - timedelta(hours=1)).isoformat(),
        "affected": [{"service": "S3", "resource": resource, "region": "eu-west-2"}],
    }


def cert(days, domain="app.example.com", status="ISSUED"):
    return {
        "resource_id": "arn:cert", "resource_name": domain, "region": "eu-west-2",
        "metrics": {"days_until_expiry": days},
        "dimensions": {"status": status, "domain": domain},
    }


def entry(result, entry_id):
    return next(e for e in result["entries"] if e["id"].startswith(entry_id))


class TestBreachClock:
    def test_an_exposure_starts_a_72_hour_clock_from_when_we_saw_it(self):
        result = calendar.build({}, [incident(detected=NOW - timedelta(hours=2))], now=NOW)
        e = entry(result, "ico-72h")
        assert e["kind"] == calendar.DEADLINE
        assert e["due_at"] == (NOW + timedelta(hours=70)).isoformat()
        assert "customer-exports" in e["title"]
        assert e["source"].startswith("https://ico.org.uk")

    def test_a_clock_that_has_run_out_is_marked_overdue(self):
        result = calendar.build({}, [incident(detected=NOW - timedelta(hours=80))], now=NOW)
        e = entry(result, "ico-72h")
        assert e["overdue"] is True and e["urgency"] == "overdue"
        assert result["overdue"] == 1

    def test_the_wording_allows_for_no_personal_data_being_involved(self):
        # Article 33 does not require a report when there is no risk. The
        # calendar must not tell a customer to report something regardless.
        e = entry(calendar.build({}, [incident()], now=NOW), "ico-72h")
        assert "unless it is unlikely to risk" in e["detail"]
        assert "record that decision" in e["detail"]

    def test_incidents_that_expose_nothing_start_no_clock(self):
        result = calendar.build({}, [incident(kind="root_login_without_mfa")], now=NOW)
        assert [e for e in result["entries"] if e["kind"] == calendar.DEADLINE] == []

    def test_an_incident_with_no_detection_time_starts_no_clock(self):
        broken = incident()
        broken["detected_at"] = None
        assert [e for e in calendar.build({}, [broken], now=NOW)["entries"]
                if e["kind"] == calendar.DEADLINE] == []


class TestExpiries:
    def test_a_certificate_expiry_becomes_a_dated_entry(self):
        result = calendar.build({"acm": [cert(20)]}, [], now=NOW)
        e = entry(result, "cert-expiry")
        assert e["kind"] == calendar.EXPIRY
        assert e["days_remaining"] == 20
        assert e["urgency"] == "scheduled"
        assert result["due_within_14_days"] == 0

    def test_an_expiry_inside_a_fortnight_is_flagged_as_soon(self):
        e = entry(calendar.build({"acm": [cert(9)]}, [], now=NOW), "cert-expiry")
        assert e["urgency"] == "soon"

    def test_a_certificate_with_no_expiry_reported_is_left_out(self):
        bare = cert(0)
        bare["metrics"] = {}
        assert [e for e in calendar.build({"acm": [bare]}, [], now=NOW)["entries"]
                if e["kind"] == calendar.EXPIRY] == []

    def test_certificates_that_are_not_issued_are_left_out(self):
        assert [e for e in calendar.build({"acm": [cert(10, status="PENDING_VALIDATION")]}, [], now=NOW)["entries"]
                if e["kind"] == calendar.EXPIRY] == []


class TestSelfDeclaredDates:
    def test_a_missing_date_says_so_instead_of_inventing_one(self):
        result = calendar.build({}, [], profile={}, now=NOW)
        e = entry(result, "renewal:cyber_essentials")
        assert e["due_at"] is None
        assert e["urgency"] == "unknown"
        assert "Add your date" in e["detail"]
        assert result["awaiting_your_date"] == 2

    def test_a_date_the_customer_gave_us_is_tracked(self):
        profile = {"cyber_essentials_expires_at": (NOW + timedelta(days=30)).isoformat()}
        e = entry(calendar.build({}, [], profile=profile, now=NOW), "renewal:cyber_essentials")
        assert e["days_remaining"] == 30
        assert "Add your date" not in e["detail"]

    def test_an_unreadable_date_is_treated_as_missing(self):
        profile = {"ico_fee_due_at": "next spring"}
        e = entry(calendar.build({}, [], profile=profile, now=NOW), "renewal:ico_fee")
        assert e["due_at"] is None


class TestOrdering:
    def test_the_most_pressing_thing_is_first(self):
        result = calendar.build(
            {"acm": [cert(200)]},
            [incident(detected=NOW - timedelta(hours=80))],
            profile={"ico_fee_due_at": (NOW + timedelta(days=3)).isoformat()},
            now=NOW,
        )
        kinds = [e["urgency"] for e in result["entries"]]
        assert kinds[0] == "overdue"
        assert kinds.index("soon") < kinds.index("scheduled")

    def test_an_account_with_nothing_due_has_only_the_dates_it_owes_us(self):
        result = calendar.build({}, [], now=NOW)
        assert {e["kind"] for e in result["entries"]} == {calendar.RENEWAL}
        assert result["overdue"] == 0


@pytest.mark.asyncio
class TestEndpoints:
    async def test_calendar_endpoint_combines_account_data_and_profile(self):
        ts = MagicMock()
        ts.get_service_inventory.side_effect = lambda cid, svc, *a: [cert(5)] if svc == "acm" else []
        db = MagicMock()
        db.get_customer.return_value = {"ico_fee_due_at": (NOW + timedelta(days=2)).isoformat()}
        with patch("routers.security.TimestreamQueryService", return_value=ts), \
             patch("routers.security.DynamoDBService", return_value=db):
            result = await security.get_calendar(customer=CTX)
        titles = [e["title"] for e in result["entries"]]
        assert any("TLS certificate" in t for t in titles)
        assert any("ICO data protection fee" in t for t in titles)

    async def test_renewal_dates_are_validated_before_they_are_stored(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            security.RenewalDates(cyber_essentials_expires_at="whenever")

    async def test_renewal_dates_are_saved_to_the_profile(self):
        db = MagicMock()
        db.get_customer.return_value = {"customer_id": "TT-1"}
        with patch("routers.security.DynamoDBService", return_value=db):
            result = await security.set_renewals(
                security.RenewalDates(cyber_essentials_expires_at="2027-03-31"), customer=CTX)
        assert result["status"] == "saved"
        assert db.update_customer.call_args[0][1]["cyber_essentials_expires_at"] == "2027-03-31"

    async def test_recheck_reports_the_control_and_records_what_changed(self):
        ts = MagicMock()
        ts.get_service_inventory.side_effect = lambda cid, svc, *a: (
            [{"resource_id": "iam", "resource_name": "iam", "region": "eu-west-2",
              "metrics": {"root_mfa_active": "true"}, "dimensions": {}}] if svc == "iam" else []
        )
        with patch("routers.security.TimestreamQueryService", return_value=ts), \
             patch("routers.security.DynamoDBService", return_value=MagicMock()), \
             patch("routers.security.evidence_recorder.record_for_customer", return_value=1):
            result = await security.recheck_control(control_id="IAM-02", customer=CTX)
        assert result["control"]["id"] == "IAM-02"
        assert result["control"]["status"] == "pass"
        assert result["evidence_entries_written"] == 1
        assert "give the agent one collection cycle" in result["note"]

    async def test_recheck_of_a_control_that_does_not_exist_is_a_404(self):
        from fastapi import HTTPException
        ts = MagicMock()
        ts.get_service_inventory.return_value = []
        with patch("routers.security.TimestreamQueryService", return_value=ts), \
             patch("routers.security.DynamoDBService", return_value=MagicMock()), \
             patch("routers.security.evidence_recorder.record_for_customer", return_value=0):
            with pytest.raises(HTTPException) as raised:
                await security.recheck_control(control_id="ZZ-99", customer=CTX)
        assert raised.value.status_code == 404

    async def test_topology_endpoint_explains_what_the_edges_mean(self):
        ts = MagicMock()
        ts.get_service_inventory.return_value = []
        with patch("routers.security.TimestreamQueryService", return_value=ts):
            result = await security.get_topology(customer=CTX)
        assert result["nodes"] == [] and result["edges"] == []
        assert "never claims two resources do talk" in result["confidence_note"]
