"""What each run collects, and that a run cannot outlive its schedule.

The agent ran every collector in 17 regions plus Cost Explorer every 5
minutes. Runs took up to 88 minutes, stacked nine deep, and ran up $167 in
twelve days in a small account, $74 of it Cost Explorer requests alone.
"""
from datetime import datetime, timedelta, timezone

import pytest

import main
from collectors.cost_explorer import CostExplorerCollector
from utils.schedule import is_due, run_slot

MIDNIGHT = datetime(2026, 9, 13, 0, 0, tzinfo=timezone.utc)


def day_of_runs(interval, jitter=timedelta(0)):
    return [MIDNIGHT + timedelta(minutes=interval * i) + jitter for i in range(24 * 60 // interval)]


class TestSlots:
    def test_eventbridge_jitter_either_side_lands_in_the_same_slot(self):
        on_time = MIDNIGHT + timedelta(minutes=5)
        assert run_slot(on_time - timedelta(seconds=2), 5) == run_slot(on_time, 5)
        assert run_slot(on_time + timedelta(seconds=40), 5) == run_slot(on_time, 5)

    @pytest.mark.parametrize("interval", [5, 10, 15, 30, 60])
    @pytest.mark.parametrize("jitter", [timedelta(seconds=-3), timedelta(0), timedelta(seconds=50)])
    def test_six_hourly_job_runs_exactly_four_times_a_day(self, interval, jitter):
        runs = [t for t in day_of_runs(interval, jitter) if is_due(t, interval, 360)]
        assert len(runs) == 4

    @pytest.mark.parametrize("interval", [5, 15])
    def test_every_run_job_is_always_due(self, interval):
        assert all(is_due(t, interval, interval) for t in day_of_runs(interval))


class TestPlan:
    @pytest.mark.parametrize("interval", [5, 15])
    def test_cost_explorer_four_times_a_day_not_every_run(self, interval):
        runs = day_of_runs(interval)
        with_cost = [t for t in runs if CostExplorerCollector in main.plan_run(t, interval)[1]]
        assert len(with_cost) == 4
        # At 5 minutes that was 288 runs x 3 billed requests a day.
        assert len(with_cost) * 3 == 12

    def test_other_global_collectors_run_every_time(self):
        others = [c for c in main.GLOBAL_COLLECTORS if c is not CostExplorerCollector]
        for t in day_of_runs(15):
            assert set(others) <= set(main.plan_run(t, 15)[1])

    @pytest.mark.parametrize("interval,expected", [(5, 48), (15, 48)])
    def test_all_regions_swept_every_30_minutes(self, interval, expected):
        assert sum(main.plan_run(t, interval)[0] for t in day_of_runs(interval)) == expected


class TestDeadline:
    def test_run_ends_before_the_next_one_starts(self):
        assert main.deadline_seconds(15) == 14 * 60
        assert main.deadline_seconds(5) < 5 * 60

    def test_never_unreasonably_short(self):
        assert main.deadline_seconds(1) == main.MIN_DEADLINE_SECONDS


def test_a_stuck_region_does_not_hold_the_run_open(monkeypatch):
    import threading
    from unittest.mock import MagicMock

    release = threading.Event()
    published, exited = [], []

    def collect_region(session, region, customer_id):
        if region == "ap-south-1":
            release.wait(5)          # a call that hangs past the deadline
            return [], 0
        return [MagicMock(name=f"rec-{region}")], 0

    config = MagicMock(customer_id="TT-1", aws_region="eu-west-2", run_interval_minutes=5,
                       ingest_queue_url="q", api_key="k", log_level="INFO")
    monkeypatch.setattr(main, "load_config", lambda: config)
    monkeypatch.setattr(main, "configure_logging", lambda level: None)
    monkeypatch.setattr(main, "boto3", MagicMock())
    monkeypatch.setattr(main, "plan_run", lambda now, i: (True, []))
    monkeypatch.setattr(main, "discover_active_regions", lambda s: ["eu-west-2", "ap-south-1"])
    monkeypatch.setattr(main, "collect_region", collect_region)
    monkeypatch.setattr(main, "collect_global", lambda *a, **k: ([], 0))
    monkeypatch.setattr(main, "deadline_seconds", lambda i: 0.3)
    monkeypatch.setattr(main, "SQSPublisher", lambda **kw: MagicMock(publish_batch=published.extend))
    monkeypatch.setattr(main.os, "_exit", exited.append)

    main.main()
    release.set()

    assert exited == [0]
    heartbeat = published[-1]
    assert heartbeat.metric_name == "heartbeat"
    assert heartbeat.dimensions["total_errors"] == 1        # the unfinished region
    assert len(published) == 2                              # eu-west-2's record + heartbeat
