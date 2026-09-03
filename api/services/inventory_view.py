"""Turning a folded resource into the fields a dashboard page renders.

TimestreamQueryService.get_service_inventory returns a resource as the agent
described it: a bag of metrics keyed by metric name, and a bag of dimensions
keyed by whatever the collector called them. Every page wants something
narrower and differently named — the storage page wants `object_count`, not
`metrics["number_of_objects"]`.

The routers do that translation, and these helpers exist so that each one is a
short list of field names rather than the same defensive parsing six times.

The rule they encode: a value that was never collected is None, never a
plausible-looking zero. The storage page decides whether a bucket is public by
reading `public_access_blocked`, and a missing field that arrives as False
labels every bucket in the account Public. Absent and "we looked, and the
answer is no" are different answers and the UI is entitled to tell them apart.
"""
from typing import Any, Dict, Optional

_TRUE = {"true", "1", "yes", "enabled"}
_FALSE = {"false", "0", "no", "disabled"}


def dim(resource: Dict[str, Any], key: str, default: str = "") -> str:
    """A dimension as text."""
    value = (resource.get("dimensions") or {}).get(key)
    return default if value is None else str(value)


def flag(resource: Dict[str, Any], key: str) -> Optional[bool]:
    """A dimension as a boolean, or None if it was never collected.

    Collectors send booleans through dimensions, which are strings by the time
    they reach DynamoDB, so "False" arrives as a non-empty string and is
    truthy in both Python and JavaScript. Read naively, every bucket in an
    account looks encrypted and versioned.
    """
    value = (resource.get("dimensions") or {}).get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return None


def num(resource: Dict[str, Any], key: str) -> Optional[float]:
    """A metric as a number, or None if it was never collected."""
    value = (resource.get("metrics") or {}).get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def text(resource: Dict[str, Any], key: str, default: str = "") -> str:
    """A metric as text — event-table values are strings such as "active"."""
    value = (resource.get("metrics") or {}).get(key)
    return default if value is None else str(value)
