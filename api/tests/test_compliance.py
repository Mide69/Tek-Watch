"""Unit tests for the compliance rule engine."""
from services import compliance


def res(resource_id, metrics=None, dims=None, **extra):
    return {
        "resource_id": resource_id,
        "resource_name": extra.pop("resource_name", resource_id),
        "region": extra.pop("region", "eu-west-2"),
        "metrics": metrics or {},
        "dimensions": dims or {},
        "last_seen": "2026-09-11T10:00:00+00:00",
        **extra,
    }


def bucket(name, blocked="True", encrypted="True", versioned="True"):
    dims = {"encryption_enabled": encrypted, "versioning_enabled": versioned}
    if blocked is not None:
        dims["public_access_blocked"] = blocked
    return res(name, {"bucket_state": "active"}, dims)


def database(name, multi_az="True", backup_days=7):
    return res(name, {"db_instance_status": "available"},
               {"engine": "postgres", "multi_az": multi_az, "backup_retention_days": backup_days})


def load_balancer(name, zones=2):
    return res(name, {"load_balancer_state": "active"},
               {"type": "application", "availability_zone_count": zones})


def healthy_inventory():
    return {
        "s3": [bucket("data"), bucket("logs")],
        "iam": [res("iam-summary", {
            "users_without_mfa_count": 0,
            "access_keys_older_than_90_days": 0,
            "root_mfa_active": "true",
        })],
        "acm": [res("arn:cert", {"days_until_expiry": 80}, {"status": "ISSUED", "domain": "a.example"})],
        "guardduty": [res("det-1", {"detector_enabled": 1, "findings_high_count": 0, "findings_critical_count": 0})],
        "cloudtrail": [res("cloudtrail-trails-eu-west-2", {"trails_logging_count": 1})],
        "rds": [database("prod-db")],
        "elb": [load_balancer("public-alb")],
        "cloudwatch_alarms": [res("alarm-cpu", {"alarm_state": "OK"})],
    }


def control(report, cid):
    return next(c for c in report["controls"] if c["id"] == cid)


def framework(report, fid):
    return next(f for f in report["frameworks"] if f["id"] == fid)


class TestNoData:
    def test_nothing_collected_passes_nothing(self):
        report = compliance.evaluate({})
        assert all(c["status"] != compliance.PASS for c in report["controls"])

    def test_scores_are_none_not_zero_or_hundred(self):
        report = compliance.evaluate({})
        assert all(f["score"] is None for f in report["frameworks"])

    def test_disclaimer_always_present(self):
        assert "not a certification" in compliance.evaluate({})["disclaimer"]

    def test_frameworks_are_the_four_we_can_evidence(self):
        report = compliance.evaluate(healthy_inventory())
        assert {f["id"] for f in report["frameworks"]} == {
            "uk_gdpr", "cyber_essentials", "iso27001", "fca_ps21_3",
        }


class TestHealthyAccount:
    def test_every_check_passes(self):
        report = compliance.evaluate(healthy_inventory())
        assert {c["status"] for c in report["controls"]} == {compliance.PASS}

    def test_every_framework_scores_100(self):
        report = compliance.evaluate(healthy_inventory())
        assert [f["score"] for f in report["frameworks"]] == [100, 100, 100, 100]


class TestS3:
    def test_public_bucket_fails_and_is_named(self):
        inv = healthy_inventory()
        inv["s3"].append(bucket("marketing", blocked="False"))
        c = control(compliance.evaluate(inv), "S3-01")
        assert c["status"] == compliance.FAIL
        assert [f["resource"] for f in c["findings"]] == ["marketing"]

    def test_unreadable_public_access_is_unknown(self):
        inv = healthy_inventory()
        inv["s3"] = [bucket("data", blocked=None)]
        assert control(compliance.evaluate(inv), "S3-01")["status"] == compliance.UNKNOWN

    def test_unencrypted_bucket_fails(self):
        inv = healthy_inventory()
        inv["s3"].append(bucket("plain", encrypted="False"))
        assert control(compliance.evaluate(inv), "S3-02")["status"] == compliance.FAIL

    def test_no_buckets_is_not_applicable(self):
        inv = healthy_inventory()
        inv["s3"] = []
        assert control(compliance.evaluate(inv), "S3-01")["status"] == compliance.NOT_APPLICABLE


class TestIAM:
    # root_mfa_active arrives as the text "true"/"false"; reading it as a
    # number made it unknown for every customer.
    def test_root_mfa_false_string_fails(self):
        inv = healthy_inventory()
        inv["iam"][0]["metrics"]["root_mfa_active"] = "false"
        assert control(compliance.evaluate(inv), "IAM-02")["status"] == compliance.FAIL

    def test_root_mfa_true_string_passes(self):
        assert control(compliance.evaluate(healthy_inventory()), "IAM-02")["status"] == compliance.PASS

    def test_users_without_mfa_fail_with_count(self):
        inv = healthy_inventory()
        inv["iam"][0]["metrics"]["users_without_mfa_count"] = 3
        c = control(compliance.evaluate(inv), "IAM-01")
        assert c["status"] == compliance.FAIL
        assert "3 IAM users" in c["detail"]

    def test_bool_metric_reads_text_and_numbers(self):
        assert compliance.bool_metric(res("x", {"m": "True"}), "m") is True
        assert compliance.bool_metric(res("x", {"m": 0}), "m") is False
        assert compliance.bool_metric(res("x", {}), "m") is None


class TestACM:
    def test_only_issued_certificates_count(self):
        inv = healthy_inventory()
        inv["acm"] = [res("arn:pending", {"days_until_expiry": -1}, {"status": "PENDING_VALIDATION"})]
        assert control(compliance.evaluate(inv), "ACM-01")["status"] == compliance.NOT_APPLICABLE

    def test_certificate_inside_30_days_fails(self):
        inv = healthy_inventory()
        inv["acm"].append(res("arn:soon", {"days_until_expiry": 12}, {"status": "ISSUED", "domain": "soon.example"}))
        c = control(compliance.evaluate(inv), "ACM-01")
        assert c["status"] == compliance.FAIL
        assert c["findings"] == [{"resource": "soon.example", "detail": "Expires in 12 days"}]


class TestGuardDuty:
    def test_off_everywhere_fails(self):
        inv = healthy_inventory()
        inv["guardduty"] = [res("guardduty-eu-west-2", {"detector_enabled": 0})]
        report = compliance.evaluate(inv)
        assert control(report, "GD-01")["status"] == compliance.FAIL
        assert control(report, "GD-02")["status"] == compliance.NOT_APPLICABLE

    def test_older_agent_counts_imply_enabled(self):
        inv = healthy_inventory()
        inv["guardduty"] = [res("det-1", {"findings_high_count": 0})]
        assert control(compliance.evaluate(inv), "GD-01")["status"] == compliance.PASS

    def test_open_high_findings_fail(self):
        inv = healthy_inventory()
        inv["guardduty"][0]["metrics"]["findings_high_count"] = 2
        assert control(compliance.evaluate(inv), "GD-02")["status"] == compliance.FAIL


class TestCloudTrail:
    def test_no_trail_logging_fails(self):
        inv = healthy_inventory()
        inv["cloudtrail"] = [res("cloudtrail-trails-eu-west-2", {"trails_logging_count": 0})]
        assert control(compliance.evaluate(inv), "CT-01")["status"] == compliance.FAIL

    def test_not_reported_is_unknown(self):
        inv = healthy_inventory()
        inv["cloudtrail"] = [res("cloudtrail-eu-west-2", {"high_risk_events_24h": 0})]
        assert control(compliance.evaluate(inv), "CT-01")["status"] == compliance.UNKNOWN


class TestScoring:
    def test_unknown_checks_are_left_out_of_the_score(self):
        inv = healthy_inventory()
        inv["iam"] = []                                  # 3 IAM checks become unknown
        fw = framework(compliance.evaluate(inv), "cyber_essentials")
        # Cyber Essentials maps S3-01 plus three IAM checks: one evaluated, passed.
        assert (fw["passed"], fw["failed"], fw["unknown"], fw["score"]) == (1, 0, 3, 100)

    def test_score_is_share_of_evaluated_checks(self):
        inv = healthy_inventory()
        inv["s3"].append(bucket("marketing", blocked="False"))
        fw = framework(compliance.evaluate(inv), "cyber_essentials")
        assert (fw["passed"], fw["failed"], fw["score"]) == (3, 1, 75)

    def test_failures_listed_first(self):
        inv = healthy_inventory()
        inv["cloudtrail"] = [res("t", {"trails_logging_count": 0})]
        assert compliance.evaluate(inv)["controls"][0]["id"] == "CT-01"


def test_load_inventory_reads_each_service():
    calls = []

    class FakeTS:
        def get_service_inventory(self, cid, service, window):
            calls.append((cid, service, window))
            return []

    inv = compliance.load_inventory(FakeTS(), "TT-1")
    assert set(inv) == set(compliance.INVENTORY_SERVICES)
    assert all(c[0] == "TT-1" and c[2] == "24h" for c in calls)


class TestOperationalResilience:
    """PS21/3 evidence, and the limits of it.

    A configuration scan cannot judge operational resilience: impact tolerances
    and scenario testing are governance. What it can do is evidence the
    technical half a firm needs when it maps the resources behind a service.
    """

    def test_ps21_3_says_what_it_does_not_cover(self):
        fw = framework(compliance.evaluate(healthy_inventory()), "fca_ps21_3")
        assert fw["scope"] == "technical_evidence_only"
        note = fw["scope_note"].lower()
        assert "impact tolerance" in note and "scenario testing" in note

    def test_single_zone_database_fails_and_is_named(self):
        inv = healthy_inventory()
        inv["rds"].append(database("reporting-db", multi_az="False"))
        c = control(compliance.evaluate(inv), "RES-01")
        assert c["status"] == compliance.FAIL
        assert [f["resource"] for f in c["findings"]] == ["reporting-db"]

    def test_database_without_backups_fails_as_critical(self):
        inv = healthy_inventory()
        inv["rds"] = [database("prod-db", backup_days=0)]
        c = control(compliance.evaluate(inv), "RES-02")
        assert c["status"] == compliance.FAIL
        assert c["severity"] == "critical"

    def test_unreported_backup_retention_is_unknown_not_a_pass(self):
        inv = healthy_inventory()
        inv["rds"] = [res("old-agent-db", {"db_instance_status": "available"},
                          {"engine": "mysql", "multi_az": "True"})]
        assert control(compliance.evaluate(inv), "RES-02")["status"] == compliance.UNKNOWN

    def test_no_databases_is_not_applicable(self):
        inv = healthy_inventory()
        inv["rds"] = []
        for cid in ("RES-01", "RES-02"):
            assert control(compliance.evaluate(inv), cid)["status"] == compliance.NOT_APPLICABLE

    def test_single_zone_load_balancer_fails(self):
        inv = healthy_inventory()
        inv["elb"] = [load_balancer("edge", zones=1)]
        c = control(compliance.evaluate(inv), "RES-03")
        assert c["status"] == compliance.FAIL
        assert c["findings"][0]["detail"] == "1 availability zone"

    def test_no_alarms_at_all_fails(self):
        inv = healthy_inventory()
        inv["cloudwatch_alarms"] = []
        assert control(compliance.evaluate(inv), "RES-04")["status"] == compliance.FAIL

    def test_resilience_controls_reference_ps21_3(self):
        report = compliance.evaluate(healthy_inventory())
        for cid in ("RES-01", "RES-02", "RES-03", "RES-04"):
            frameworks = {r["framework"] for r in control(report, cid)["references"]}
            assert "fca_ps21_3" in frameworks

    def test_not_applicable_resources_are_left_out_of_the_score(self):
        inv = healthy_inventory()
        inv["rds"] = []
        inv["elb"] = []
        fw = framework(compliance.evaluate(inv), "fca_ps21_3")
        assert fw["score"] == 100
        assert fw["passed"] + fw["failed"] < fw["total"]
