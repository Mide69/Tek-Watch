"""Unit tests for TekWatch's own statistical anomaly detector."""
from datetime import datetime, timedelta, timezone

from services.alerting import detector

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def base(metric="cpu_utilization_percent", mean=40.0, std=5.0, samples=2000,
         age=timedelta(days=7), service="ec2", resource="i-1"):
    return {
        "service": service, "resource_id": resource, "metric_name": metric,
        "avg_value": mean, "stddev_value": std, "samples": samples,
        "first_time": (NOW - age).isoformat(),
    }


def recent(value, metric="cpu_utilization_percent", service="ec2", resource="i-1"):
    return {"service": service, "resource_id": resource, "metric_name": metric,
            "value": value, "time": NOW.isoformat()}


def run(baseline, rows):
    return detector.detect(baseline, rows, now=NOW)


class TestZScore:
    def test_five_sigma_spike_is_high(self):
        [a] = run([base()], [recent(66)])
        assert (a.kind, a.severity, a.z_score) == ("spike", "high", 5.2)

    def test_three_sigma_is_medium(self):
        [a] = run([base()], [recent(56)])
        assert a.severity == "medium"

    def test_inside_three_sigma_is_normal(self):
        assert run([base()], [recent(54)]) == []

    def test_uses_mean_of_the_last_hour_not_one_sample(self):
        # One reading of 90 among normal ones is noise, not an incident.
        assert run([base()], [recent(90)] + [recent(40)] * 11) == []

    def test_drop_is_reported_for_ordinary_metrics(self):
        [a] = run([base(mean=400, std=20, metric="request_count")], [recent(300, metric="request_count")])
        assert a.kind == "drop"

    def test_error_drop_is_a_recovery_not_an_anomaly(self):
        assert run([base(metric="error_count", mean=50, std=5)], [recent(0, metric="error_count")]) == []

    def test_error_spike_is_reported(self):
        [a] = run([base(metric="error_count", mean=2, std=1)], [recent(20, metric="error_count")])
        assert a.severity == "high"


class TestStepChange:
    def test_flat_zero_to_anything_is_high(self):
        [a] = run([base(metric="users_without_mfa_count", mean=0, std=0)],
                  [recent(1, metric="users_without_mfa_count")])
        assert (a.kind, a.severity, a.z_score) == ("step", "high", None)

    def test_small_move_from_flat_is_ignored(self):
        assert run([base(mean=100, std=0)], [recent(130)]) == []

    def test_doubling_from_flat_is_medium(self):
        [a] = run([base(mean=100, std=0)], [recent(200)])
        assert a.severity == "medium"

    def test_unchanged_flat_is_normal(self):
        assert run([base(mean=4, std=0)], [recent(4)]) == []


class TestGuards:
    def test_needs_a_day_of_history(self):
        assert run([base(age=timedelta(hours=6))], [recent(500)]) == []

    def test_needs_enough_samples(self):
        assert run([base(samples=5)], [recent(500)]) == []

    def test_trending_metrics_are_skipped(self):
        assert run([base(metric="bucket_size_bytes", mean=10, std=1)],
                   [recent(10_000, metric="bucket_size_bytes")]) == []

    def test_metric_without_recent_data_is_skipped(self):
        assert run([base()], []) == []

    def test_every_metric_is_examined_not_the_first_100(self):
        baseline = [base(resource=f"i-{n}") for n in range(300)]
        rows = [recent(40, resource=f"i-{n}") for n in range(299)] + [recent(90, resource="i-299")]
        [a] = run(baseline, rows)
        assert a.resource_id == "i-299"

    def test_bad_values_are_ignored(self):
        assert run([base()], [recent("n/a"), recent(None)]) == []


def test_high_severity_first():
    baseline = [base(resource="a"), base(resource="b")]
    found = run(baseline, [recent(56, resource="a"), recent(80, resource="b")])
    assert [a.resource_id for a in found] == ["b", "a"]


class TestDescribe:
    def test_spike_wording_uses_the_numbers(self):
        [a] = run([base()], [recent(66)])
        description, _ = detector.describe(a)
        assert "66" in description and "40" in description and "5.2 standard deviations above" in description

    def test_security_metric_points_to_cloudtrail(self):
        [a] = run([base(metric="users_without_mfa_count", mean=0, std=0)],
                  [recent(2, metric="users_without_mfa_count")])
        _, recommendation = detector.describe(a)
        assert "CloudTrail" in recommendation
