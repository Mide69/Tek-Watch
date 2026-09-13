"""Which parts of the collection are due on this run.

The agent is a fresh Fargate task every time, with nowhere to remember what
the last run did. So "due" is worked out from the clock alone: each run is
rounded to the nearest slot of the schedule interval, and a job that should
happen every N minutes runs on every slot divisible by N / interval.

Rounding to the nearest slot, not down, is what keeps this exact. EventBridge
fires a few seconds either side of the minute (runs were seen at 18:00:00,
18:04:58 and 18:10:01), and rounding down would put 18:04:58 in the 18:00
slot and run a six-hourly job twice.
"""
from datetime import datetime


def run_slot(now: datetime, interval_minutes: int) -> int:
    """Index of the schedule slot this run belongs to, counted from the epoch."""
    interval = max(1, interval_minutes) * 60
    return int((now.timestamp() + interval / 2) // interval)


def is_due(now: datetime, interval_minutes: int, every_minutes: int) -> bool:
    """True on exactly one run in each `every_minutes` period."""
    runs_per_period = max(1, round(every_minutes / max(1, interval_minutes)))
    return run_slot(now, interval_minutes) % runs_per_period == 0
