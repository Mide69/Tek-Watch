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

    def test_fca_is_not_claimed(self):
        report = compliance.evaluate(healthy_inventory())
        names = " ".join(f["name"] for f in report["frameworks"]).lower()
        assert "fca" not in names
        assert {f["id"] for f in report["frameworks"]} == {"uk_gdpr", "cyber_essentials", "iso27001"}


class TestHealthyAccount:
    def test_every_check_passes(self):
        report = compliance.evaluate(healthy_inventory())
        assert {c["status"] for c in report["controls"]} == {compliance.PASS}

    def test_every_framework_scores_100(self):
        report = compliance.evaluate(healthy_inventory())
        assert [f["score"] for f in report["frameworks"]] == [100, 100, 100]


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
