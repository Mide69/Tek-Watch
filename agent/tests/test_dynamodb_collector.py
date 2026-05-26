"""Unit tests for the DynamoDBCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.dynamodb import DynamoDBCollector


def make_table_detail(name="users", status="ACTIVE", item_count=500, size_bytes=1024000):
    return {
        "Table": {
            "TableName": name,
            "TableStatus": status,
            "ItemCount": item_count,
            "TableSizeBytes": size_bytes,
            "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
            "ProvisionedThroughput": {"ReadCapacityUnits": 0, "WriteCapacityUnits": 0},
        }
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ddb = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: ddb if svc == "dynamodb" else cw
    c = DynamoDBCollector(session, "eu-west-1", "TT-0001")
    c._ddb = ddb
    c._cw = cw
    return c, ddb, cw


class TestDynamoDBCollector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "dynamodb"

    def test_no_tables_returns_empty(self, collector):
        c, ddb, _ = collector
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": []}]
        assert c.collect() == []

    def test_table_status_and_size_emitted(self, collector):
        c, ddb, cw = collector
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["users"]}]
        ddb.describe_table.return_value = make_table_detail()
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        metric_names = {r.metric_name for r in records}
        assert "table_status" in metric_names
        assert "table_size_bytes" in metric_names
        assert "item_count" in metric_names

    def test_table_status_value_correct(self, collector):
        c, ddb, cw = collector
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["users"]}]
        ddb.describe_table.return_value = make_table_detail(status="ACTIVE")
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        status_rec = next(r for r in records if r.metric_name == "table_status")
        assert status_rec.metric_value == "ACTIVE"

    def test_inactive_table_skips_cw(self, collector):
        c, ddb, cw = collector
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["users"]}]
        ddb.describe_table.return_value = make_table_detail(status="CREATING")

        records = c.collect()
        assert len(records) == 3  # status + size + item_count only
        cw.get_metric_statistics.assert_not_called()

    def test_cw_metric_emitted_for_active_table(self, collector):
        c, ddb, cw = collector
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["orders"]}]
        ddb.describe_table.return_value = make_table_detail(name="orders")
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Sum": 42.0}]
        }
        records = c.collect()
        assert len(records) > 3

    def test_client_error_returns_empty(self, collector):
        c, ddb, _ = collector
        ddb.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListTables",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, ddb, cw = collector
        ddb.get_paginator.return_value.paginate.return_value = [{"TableNames": ["users"]}]
        ddb.describe_table.return_value = make_table_detail()
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
