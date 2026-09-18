"""The database and root-login incident chains, and operational impact.

The S3 and audit-logging chains are covered in test_correlation.py.
"""
from datetime import datetime, timedelta, timezone

from services import correlation, topology

NOW = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


def event(name, resource, when, user="deploy-bot", ip="203.0.113.9"):
    return {
        "resource_id": f"evt-{name}-{resource}", "resource_name": name, "region": "eu-west-2",
        "metrics": {"high_risk_event": name},
        "dimensions": {
            "event_name": name, "username": user, "source_ip": ip,
            "resource_name": resource, "event_time": when.isoformat(),
        },
    }


def database(name="prod-db", public="True", engine="postgres", storage="100", multi_az="true"):
    dims = {"engine": engine, "allocated_storage_gb": storage, "multi_az": multi_az}
    if public is not None:
        dims["publicly_accessible"] = public
    return {
        "resource_id": name, "resource_name": name, "region": "eu-west-2",
        "metrics": {"db_instance_status": "available"}, "dimensions": dims,
        "last_seen": NOW.isoformat(),
    }


def iam(root_mfa="false"):
    metrics = {"total_users": 4}
    if root_mfa is not None:
        metrics["root_mfa_active"] = root_mfa
    return [{"resource_id": "iam-summary", "resource_name": "iam_summary",
             "metrics": metrics, "dimensions": {}, "last_seen": NOW.isoformat()}]


def only(incidents, kind):
    return [i for i in incidents if i["type"] == kind]


class TestPublicDatabase:
    def test_public_database_with_a_cause_is_critical(self):
        inv = {
            "rds": [database()],
            "cloudtrail": [event("ModifyDBInstance", "prod-db", NOW - timedelta(hours=1))],
        }
        [incident] = only(correlation.correlate(inv, now=NOW), "database_publicly_reachable")
        assert incident["severity"] == "critical"
        assert incident["correlated"] is True
        assert "deploy-bot" in incident["summary"]
        assert incident["affected"] == [{"service": "RDS", "resource": "prod-db", "region": "eu-west-2"}]
        assert "--no-publicly-accessible" in incident["remediation"][0]["command"]

    def test_without_a_cause_it_is_reported_as_uncorrelated(self):
        inv = {"rds": [database()], "cloudtrail": []}
        [incident] = only(correlation.correlate(inv, now=NOW), "database_publicly_reachable")
        assert incident["correlated"] is False
        assert incident["severity"] == "high"

    def test_private_database_is_not_an_incident(self):
        inv = {"rds": [database(public="False")], "cloudtrail": []}
        assert only(correlation.correlate(inv, now=NOW), "database_publicly_reachable") == []

    def test_unknown_flag_is_not_an_incident(self):
        # An older agent does not report the field at all. Absent is not "public".
        inv = {"rds": [database(public=None)], "cloudtrail": []}
        assert only(correlation.correlate(inv, now=NOW), "database_publicly_reachable") == []

    def test_operational_impact_uses_the_collected_facts(self):
        inv = {"rds": [database()], "cloudtrail": []}
        [incident] = only(correlation.correlate(inv, now=NOW), "database_publicly_reachable")
        points = " ".join(incident["operational_impact"]["points"])
        assert "postgres" in points
        assert "100 GB" in points
        assert "multi-AZ" in points

    def test_regulatory_impact_names_uk_gdpr(self):
        inv = {"rds": [database()], "cloudtrail": []}
        [incident] = only(correlation.correlate(inv, now=NOW), "database_publicly_reachable")
        assert any(r["framework"] == "UK GDPR" for r in incident["regulatory_impact"])


class TestRootLogin:
    def test_root_signin_without_mfa_is_an_incident(self):
        inv = {
            "iam": iam(root_mfa="false"),
            "cloudtrail": [event("ConsoleLogin", "", NOW - timedelta(minutes=20), user="root")],
        }
        [incident] = only(correlation.correlate(inv, now=NOW), "root_login_without_mfa")
        assert incident["severity"] == "critical"
        assert "203.0.113.9" in incident["summary"]
        assert len(incident["chain"]) == 2

    def test_root_with_mfa_is_not_an_incident(self):
        inv = {
            "iam": iam(root_mfa="true"),
            "cloudtrail": [event("ConsoleLogin", "", NOW, user="root")],
        }
        assert only(correlation.correlate(inv, now=NOW), "root_login_without_mfa") == []

    def test_no_signin_is_a_compliance_gap_not_an_incident(self):
        # Root without MFA and nobody using it is check IAM-02, not an incident.
        inv = {"iam": iam(root_mfa="false"), "cloudtrail": []}
        assert only(correlation.correlate(inv, now=NOW), "root_login_without_mfa") == []

    def test_an_ordinary_user_signing_in_is_not_this_incident(self):
        inv = {
            "iam": iam(root_mfa="false"),
            "cloudtrail": [event("ConsoleLogin", "", NOW, user="alice")],
        }
        assert only(correlation.correlate(inv, now=NOW), "root_login_without_mfa") == []

    def test_unknown_root_mfa_state_is_not_an_incident(self):
        inv = {
            "iam": iam(root_mfa=None),
            "cloudtrail": [event("ConsoleLogin", "", NOW, user="root")],
        }
        assert only(correlation.correlate(inv, now=NOW), "root_login_without_mfa") == []


class TestOperationalImpactEverywhere:
    def bucket(self, blocked="False", objects=None, size=None):
        metrics = {"bucket_state": "active"}
        if objects is not None:
            metrics["number_of_objects"] = objects
        if size is not None:
            metrics["bucket_size_bytes"] = size
        return {
            "resource_id": "customer-exports", "resource_name": "customer-exports",
            "region": "global", "metrics": metrics,
            "dimensions": {"public_access_blocked": blocked, "bucket_region": "eu-west-2"},
            "last_seen": NOW.isoformat(),
        }

    def test_every_incident_carries_operational_impact(self):
        inv = {
            "s3": [self.bucket()],
            "rds": [database()],
            "iam": iam(root_mfa="false"),
            "cloudtrail": [
                {"resource_id": "trails", "resource_name": "trails",
                 "metrics": {"trails_logging_count": 0}, "dimensions": {}},
                event("StopLogging", "org-trail", NOW - timedelta(hours=2)),
                event("ConsoleLogin", "", NOW - timedelta(minutes=5), user="root"),
            ],
        }
        incidents = correlation.correlate(inv, now=NOW)
        assert len(incidents) == 4
        for i in incidents:
            impact = i["operational_impact"]
            assert impact["headline"]
            assert impact["points"], i["type"]

    def test_bucket_size_is_reported_in_plain_english(self):
        inv = {"s3": [self.bucket(objects=1240, size=3_221_225_472)], "cloudtrail": []}
        [incident] = only(correlation.correlate(inv, now=NOW), "s3_public_exposure")
        points = " ".join(incident["operational_impact"]["points"])
        assert "1,240 objects" in points
        assert "3.0 GB" in points

    def test_unknown_size_says_so_rather_than_guessing(self):
        inv = {"s3": [self.bucket()], "cloudtrail": []}
        [incident] = only(correlation.correlate(inv, now=NOW), "s3_public_exposure")
        points = " ".join(incident["operational_impact"]["points"])
        assert "has not been reported yet" in points


def test_load_inventory_reads_the_services_the_chains_need():
    asked = []

    class FakeTS:
        def get_service_inventory(self, cid, service, window):
            asked.append(service)
            return []

    correlation.load_inventory(FakeTS(), "TT-1")
    # The four the chains read, plus whatever the dependency graph joins up, so
    # an incident can say what else the change reaches.
    assert {"s3", "rds", "iam", "cloudtrail"} <= set(asked)
    assert set(topology.TOPOLOGY_SERVICES) <= set(asked)
