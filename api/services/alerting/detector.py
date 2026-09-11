"""TekWatch's anomaly detector.

Deciding what counts as an anomaly used to be delegated to a language model:
the 7-day baseline was computed here, then sent to Claude with a prompt asking
it to "flag anything over 2 standard deviations". That made the core of the
product a prompt, not code — untestable, non-deterministic, billed per call,
and silently limited to the first 100 rows of each input, so most of a real
account's metrics were never examined at all.

Detection is now plain statistics over every metric the agent reports. A model
is only asked, afterwards, to put the anomalies this module found into plain
English (see anomaly.py). It cannot add, remove or re-grade them.

Two tests run against each metric's 7-day baseline:

* z-score — how many standard deviations the last hour's mean sits from the
  7-day mean. 3 or more is medium, 5 or more is high.
* step change — for a metric that has been flat all week (standard deviation
  effectively zero, so a z-score is undefined), a move of 50% or more, or any
  move at all away from a baseline of exactly zero.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

MIN_HISTORY = timedelta(hours=24)
MIN_SAMPLES = 12
Z_MEDIUM = 3.0
Z_HIGH = 5.0
STEP_MEDIUM = 0.5   # 50% move away from a flat baseline
STEP_HIGH = 3.0     # 300%

# Metrics that rise or fall steadily on their own. A bucket growing, a
# certificate approaching expiry, month-to-date spend climbing: none of these
# are incidents, and flagging them trains people to ignore the alerts that are.
TRENDING_METRICS = frozenset({
    "mtd_blended_cost",
    "forecasted_monthly_cost",
    "bucket_size_bytes",
    "number_of_objects",
    "table_size_bytes",
    "item_count",
    "days_until_expiry",
    "record_set_count",
})

# Metrics where only an increase is bad news. Errors dropping to zero is a
# recovery, not an anomaly worth waking someone for.
_BAD_WHEN_HIGH = (
    "error", "fail", "throttl", "5xx", "4xx", "risk", "without_mfa",
    "older_than", "unhealthy", "latency", "age_of_oldest", "response_time",
    "non_compliant",
)


def _only_increases_matter(metric_name: str) -> bool:
    name = metric_name.lower()
    return any(token in name for token in _BAD_WHEN_HIGH)


@dataclass(frozen=True)
class Anomaly:
    service: str
    resource_id: str
    metric_name: str
    kind: str                # "spike" | "drop" | "step"
    severity: str            # "medium" | "high"
    recent_value: float
    baseline_mean: float
    baseline_stddev: float
    z_score: Optional[float]
    samples: int

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.service, self.resource_id, self.metric_name)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _recent_means(recent: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str, str], float]:
    """Mean of the last hour's readings for each metric.

    The mean rather than the latest reading: one bad sample in twelve should
    not page anyone, but a whole hour away from normal should.
    """
    sums: Dict[Tuple[str, str, str], List[float]] = {}
    for row in recent:
        key = (str(row.get("service")), str(row.get("resource_id")), str(row.get("metric_name")))
        try:
            value = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            sums.setdefault(key, []).append(value)
    return {key: sum(vals) / len(vals) for key, vals in sums.items() if vals}


def detect(
    baseline: Iterable[Dict[str, Any]],
    recent: Iterable[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> List[Anomaly]:
    """Every metric whose last hour departs from its own 7-day baseline."""
    now = now or datetime.now(timezone.utc)
    recent_by_key = _recent_means(recent)
    found: List[Anomaly] = []

    for entry in baseline:
        service = str(entry.get("service"))
        resource_id = str(entry.get("resource_id"))
        metric_name = str(entry.get("metric_name"))
        if metric_name in TRENDING_METRICS:
            continue

        key = (service, resource_id, metric_name)
        if key not in recent_by_key:
            continue

        samples = int(entry.get("samples") or 0)
        first_seen = _parse_time(entry.get("first_time"))
        # A day of history is the least that makes "normal" mean anything.
        # Without it a brand-new resource is anomalous by definition.
        if samples < MIN_SAMPLES or first_seen is None or now - first_seen < MIN_HISTORY:
            continue

        try:
            mean = float(entry.get("avg_value"))
            std = float(entry.get("stddev_value") or 0.0)
        except (TypeError, ValueError):
            continue
        value = recent_by_key[key]
        if not (math.isfinite(mean) and math.isfinite(std)):
            continue

        increases_only = _only_increases_matter(metric_name)
        flat = std <= 1e-9 * max(1.0, abs(mean))

        if flat:
            if value == mean:
                continue
            if mean == 0:
                relative = math.inf
            else:
                relative = abs(value - mean) / abs(mean)
            if relative < STEP_MEDIUM:
                continue
            if increases_only and value < mean:
                continue
            found.append(Anomaly(
                service, resource_id, metric_name, "step",
                "high" if relative >= STEP_HIGH else "medium",
                value, mean, std, None, samples,
            ))
            continue

        z = (value - mean) / std
        if abs(z) < Z_MEDIUM:
            continue
        if increases_only and z < 0:
            continue
        found.append(Anomaly(
            service, resource_id, metric_name,
            "spike" if z > 0 else "drop",
            "high" if abs(z) >= Z_HIGH else "medium",
            value, mean, std, round(z, 2), samples,
        ))

    # Worst first, so the explanation step and anyone reading the log see the
    # most important ones even if they stop reading early.
    found.sort(key=lambda a: (a.severity != "high", -(abs(a.z_score) if a.z_score is not None else 10.0)))
    return found


def _fmt(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:.4g}"


def describe(anomaly: Anomaly) -> Tuple[str, str]:
    """A plain-English description and recommendation, without any model.

    Used as-is when no explanation service is configured, and as the fallback
    whenever that service fails or returns something unusable.
    """
    metric = anomaly.metric_name.replace("_", " ")
    where = f"{anomaly.service.upper()} {anomaly.resource_id}"
    now_v, mean_v = _fmt(anomaly.recent_value), _fmt(anomaly.baseline_mean)

    if anomaly.kind == "step":
        description = (
            f"{metric} on {where} moved from a steady {mean_v} over the past week "
            f"to {now_v} in the last hour."
        )
    else:
        direction = "above" if anomaly.kind == "spike" else "below"
        description = (
            f"{metric} on {where} averaged {now_v} in the last hour, against a "
            f"7-day average of {mean_v}. That is {abs(anomaly.z_score or 0):.1f} "
            f"standard deviations {direction} normal."
        )

    name = anomaly.metric_name.lower()
    if any(t in name for t in ("risk", "mfa", "key", "policy", "finding")):
        recommendation = (
            "Check CloudTrail for the change behind this and confirm it was "
            "authorised. If nobody on your team made it, treat it as a possible "
            "security incident."
        )
    elif "cost" in name:
        recommendation = (
            "Open the Cost page to see which service drove the change, and check "
            "for new or resized resources created in the last day."
        )
    else:
        recommendation = (
            "Check what changed on this resource in the last hour: a deployment, "
            "a configuration change, or unexpected load."
        )
    return description, recommendation
