"""Unit tests for the LambdaCollector."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from collectors.lambda_ import LambdaCollector


def make_function(name="my-func", runtime="python3.11", memory=512, timeout=30):
    return {
        "FunctionName": name,
        "FunctionArn":  f"arn:aws:lambda:eu-west-2:123456789012:function:{name}",
        "Runtime":      runtime,
        "MemorySize":   memory,
        "Timeout":      timeout,
    }


@pytest.fixture
def collector():
    session     = MagicMock()
    lmb_client  = MagicMock()
    cw_client   = MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        lmb_client if svc == "lambda" else cw_client
    )
    c = LambdaCollector(session, "eu-west-2", "TT-0001")
    c._lambda = lmb_client
    c._cw     = cw_client
    return c, lmb_client, cw_client


class TestLambdaCollector:
    def test_collect_returns_inventory_record(self, collector):
        c, lmb, cw = collector
        lmb.get_paginator.return_value.paginate.return_value = [
            {"Functions": [make_function()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = [r for r in records if r.metric_name == "function_runtime"]
        assert len(inv) == 1
        assert inv[0].metric_value == "python3.11"

    def test_no_functions_returns_empty(self, collector):
        c, lmb, cw = collector
        lmb.get_paginator.return_value.paginate.return_value = [{"Functions": []}]
        assert c.collect() == []

    def test_collect_metrics_when_datapoints_present(self, collector):
        c, lmb, cw = collector
        lmb.get_paginator.return_value.paginate.return_value = [
            {"Functions": [make_function()]}
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Sum": 1200.0}]
        }
        records = c.collect()
        inv_count = [r for r in records if r.metric_name != "function_runtime"]
        assert len(inv_count) > 0

    def test_client_error_returns_empty(self, collector):
        from botocore.exceptions import ClientError
        c, lmb, cw = collector
        lmb.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "no"}}, "ListFunctions"
        )
        assert c.collect() == []

    def test_dimensions_include_runtime_and_memory(self, collector):
        c, lmb, cw = collector
        lmb.get_paginator.return_value.paginate.return_value = [
            {"Functions": [make_function(runtime="nodejs18.x", memory=1024)]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = [r for r in records if r.metric_name == "function_runtime"][0]
        assert inv.dimensions["runtime"]   == "nodejs18.x"
        assert inv.dimensions["memory_mb"] == 1024

    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "lambda"

    def test_customer_id_propagated(self, collector):
        c, lmb, cw = collector
        lmb.get_paginator.return_value.paginate.return_value = [
            {"Functions": [make_function()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)

    def test_multiple_functions_collected(self, collector):
        c, lmb, cw = collector
        fns = [make_function(f"func-{i}") for i in range(3)]
        lmb.get_paginator.return_value.paginate.return_value = [{"Functions": fns}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = [r for r in records if r.metric_name == "function_runtime"]
        assert len(inv) == 3
