"""Unit tests for cross-service incident correlation."""
from datetime import datetime, timedelta, timezone

from services import correlation

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def bucket(name, blocked):
    dims = {"bucket_region": "eu-west-2"}
    if blocked is not None:
        dims["public_access_blocked"] = blocked
    return {
        "resource_id": name, "resource_name": name, "region": "global",
        "metrics": {"bucket_state": "active"}, "dimensions": dims,
        "last_seen": NOW.isoformat(),
    }


def event(name, resource, when, user="bob", event_id=None):
    return {
        "resource_id": event_id or f"evt-{name}-{resource}-{when.isoformat()}",
        "resource_name": name, "region": "eu-west-2",
        "metrics": {"high_risk_event": name},
        "dimensions": {
            "event_name": name, "username": user, "source_ip": "203.0.113.9",
            "resource_name": resource, "event_time": when.isoformat(),
        },
        "last_seen": when.isoformat(),
    }


def trails(count):
    return {
        "resource_id": "cloudtrail-trails-eu-west-2", "resource_name": "cloudtrail-trails-eu-west-2",
        "region": "eu-west-2", "metrics": {"trails_logging_count": count}, "dimensions": {},
    }


class TestS3Exposure:
    def test_change_plus_exposure_is_one_correlated_incident(self):
        inv = {
            "s3": [bucket("customer-exports", "False")],
            "cloudtrail": [event("DeleteBucketPublicAccessBlock", "customer-exports", NOW - timedelta(hours=2))],
        }
        [incident] = correlation.correlate(inv, now=NOW)
        assert incident["correlated"] is True
        assert incident["severity"] == "critical"
        assert "bob" in incident["summary"]
        assert incident["chain"][0]["service"] == "CloudTrail"
        assert "203.0.113.9" in incident["chain"][0]["detail"]
        assert incident["affected"] == [{"service": "S3", "resource": "customer-exports", "region": "eu-west-2"}]

    def test_first_step_is_the_containment_command(self):
        inv = {
            "s3": [bucket("customer-exports", "False")],
            "cloudtrail": [event("PutBucketPolicy", "customer-exports", NOW - timedelta(hours=1))],
        }
        [incident] = correlation.correlate(inv, now=NOW)
        first = incident["remediation"][0]
        assert first["order"] == 1
        assert "put-public-access-block --bucket customer-exports" in first["command"]
        assert [s["order"] for s in incident["remediation"]] == list(range(1, len(incident["remediation"]) + 1))

    def test_gdpr_breach_notification_is_flagged(self):
        inv = {"s3": [bucket("b", "False")], "cloudtrail": []}
        [incident] = correlation.correlate(inv, now=NOW)
        refs = [r["reference"] for r in incident["regulatory_impact"]]
        assert any("Art. 33" in r for r in refs)
        assert any("Art. 32" in r for r in refs)

    def test_exposure_with_no_cause_is_reported_but_uncorrelated(self):
        inv = {"s3": [bucket("old-public", "False")], "cloudtrail": []}
        [incident] = correlation.correlate(inv, now=NOW)
        assert incident["correlated"] is False
        assert incident["severity"] == "high"
        assert "No matching change" in incident["summary"]

    def test_old_cause_is_high_not_critical(self):
        inv = {
            "s3": [bucket("b", "False")],
            "cloudtrail": [event("PutBucketAcl", "b", NOW - timedelta(days=5))],
        }
        [incident] = correlation.correlate(inv, now=NOW)
        assert incident["correlated"] is True
        assert incident["severity"] == "high"

    def test_latest_change_is_the_cause(self):
        inv = {
            "s3": [bucket("b", "False")],
            "cloudtrail": [
                event("PutBucketPolicy", "b", NOW - timedelta(hours=8), user="alice"),
                event("PutBucketAcl", "b", NOW - timedelta(hours=1), user="carol"),
            ],
        }
        [incident] = correlation.correlate(inv, now=NOW)
        assert "carol" in incident["summary"]
        assert "PutBucketAcl" in incident["title"]

    def test_blocked_bucket_is_not_an_incident(self):
        inv = {
            "s3": [bucket("b", "True")],
            "cloudtrail": [event("PutBucketPolicy", "b", NOW - timedelta(hours=1))],
        }
        assert correlation.correlate(inv, now=NOW) == []

    def test_unknown_bucket_state_is_not_an_incident(self):
        inv = {"s3": [bucket("b", None)], "cloudtrail": []}
        assert correlation.correlate(inv, now=NOW) == []

    def test_event_on_another_bucket_does_not_correlate(self):
        inv = {
            "s3": [bucket("exposed", "False")],
            "cloudtrail": [event("PutBucketPolicy", "different", NOW - timedelta(hours=1))],
        }
        [incident] = correlation.correlate(inv, now=NOW)
        assert incident["correlated"] is False


class TestLoggingDisabled:
    def test_stop_logging_and_nothing_logging_is_an_incident(self):
        inv = {"s3": [], "cloudtrail": [trails(0), event("StopLogging", "org-trail", NOW - timedelta(hours=1), user="mallory")]}
        [incident] = correlation.correlate(inv, now=NOW)
        assert incident["type"] == "audit_logging_disabled"
        assert incident["severity"] == "critical"
        assert "mallory" in incident["title"]
        assert incident["remediation"][0]["command"] == "aws cloudtrail start-logging --name org-trail"

    def test_still_logging_is_not_an_incident(self):
        inv = {"s3": [], "cloudtrail": [trails(1), event("StopLogging", "old", NOW - timedelta(hours=1))]}
        assert correlation.correlate(inv, now=NOW) == []

    def test_never_logging_without_a_cause_is_not_an_incident(self):
        # That is a compliance gap (CT-01), not something someone just did.
        assert correlation.correlate({"s3": [], "cloudtrail": [trails(0)]}, now=NOW) == []

    def test_unknown_trail_status_is_not_an_incident(self):
        inv = {"s3": [], "cloudtrail": [event("DeleteTrail", "org", NOW - timedelta(hours=1))]}
        assert correlation.correlate(inv, now=NOW) == []


def test_most_severe_first():
    inv = {
        "s3": [bucket("old-public", "False"), bucket("fresh", "False")],
        "cloudtrail": [event("PutBucketPolicy", "fresh", NOW - timedelta(hours=1))],
    }
    assert [i["severity"] for i in correlation.correlate(inv, now=NOW)] == ["critical", "high"]


def test_rollup_rows_are_not_events():
    rollup = {"resource_id": "cloudtrail-eu-west-2", "resource_name": "cloudtrail-eu-west-2",
              "metrics": {"high_risk_events_24h": 3}, "dimensions": {}}
    inv = {"s3": [bucket("b", "False")], "cloudtrail": [rollup]}
    [incident] = correlation.correlate(inv, now=NOW)
    assert incident["correlated"] is False
