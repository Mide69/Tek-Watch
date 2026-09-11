"""The 7-day baseline, computed while DynamoDB pages stream in."""
import statistics
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from services.timestream import TimestreamQueryService


def service_with_pages(*pages):
    svc = TimestreamQueryService.__new__(TimestreamQueryService)
    table = MagicMock()
    responses = []
    for i, items in enumerate(pages):
        resp = {"Items": items}
        if i < len(pages) - 1:
            resp["LastEvaluatedKey"] = {"page": i}
        responses.append(resp)
    table.query.side_effect = responses
    svc._metrics_table = table
    return svc, table


def row(value, time, metric="cpu", resource="i-1", service="ec2"):
    return {"service": service, "resource_id": resource, "metric_name": metric,
            "value": value, "time": time}


def test_matches_the_statistics_module_across_pages():
    values = [40, 42, 38, 55, 41, 39, 44]
    pages = [
        [row(v, f"2026-09-0{i + 1}T00:00:00+00:00") for i, v in enumerate(values[:4])],
        [row(v, f"2026-09-0{i + 5}T00:00:00+00:00") for i, v in enumerate(values[4:])],
    ]
    svc, table = service_with_pages(*pages)
    [summary] = svc.get_7day_summary("TT-1")
    assert summary["samples"] == 7
    assert summary["avg_value"] == pytest.approx(statistics.mean(values))
    assert summary["stddev_value"] == pytest.approx(statistics.stdev(values))
    assert summary["first_time"] == "2026-09-01T00:00:00+00:00"
    assert table.query.call_count == 2
    assert table.query.call_args_list[1].kwargs["ExclusiveStartKey"] == {"page": 0}


def test_metrics_are_kept_apart():
    svc, _ = service_with_pages([
        row(1, "2026-09-01T00:00:00+00:00", metric="a"),
        row(9, "2026-09-01T00:00:00+00:00", metric="b"),
        row(3, "2026-09-02T00:00:00+00:00", metric="a"),
    ])
    by_metric = {s["metric_name"]: s for s in svc.get_7day_summary("TT-1")}
    assert by_metric["a"]["avg_value"] == pytest.approx(2)
    assert by_metric["b"] == {**by_metric["b"], "samples": 1, "stddev_value": 0.0}


def test_bad_values_are_skipped_not_fatal():
    svc, _ = service_with_pages([row("n/a", "t1"), row(None, "t2"), row(5, "t3")])
    [summary] = svc.get_7day_summary("TT-1")
    assert summary["samples"] == 1


def test_a_failure_mid_stream_gives_no_baseline_not_part_of_one():
    svc = TimestreamQueryService.__new__(TimestreamQueryService)
    table = MagicMock()
    table.query.side_effect = [
        {"Items": [row(1, "t1")], "LastEvaluatedKey": {"page": 0}},
        ClientError({"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}}, "Query"),
    ]
    svc._metrics_table = table
    assert svc.get_7day_summary("TT-1") == []


def test_paginated_query_still_returns_every_item():
    _, table = service_with_pages([{"a": 1}], [{"a": 2}])
    items = TimestreamQueryService._paginated_query(table, key_condition=MagicMock())
    assert items == [{"a": 1}, {"a": 2}]
