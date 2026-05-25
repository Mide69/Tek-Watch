"""Unit tests for the RDSCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from collectors.rds import RDSCollector


def make_db_instance(db_id="mydb", status="available", allocated_gb=100):
    return {
        "DBInstanceIdentifier": db_id,
        "Engine": "postgres",
        "EngineVersion": "15.3",
        "DBInstanceStatus": status,
        "DBInstanceClass": "db.t3.medium",
        "MultiAZ": True,
        "AvailabilityZone": "eu-west-1a",
        "AllocatedStorage": allocated_gb,
    }


@pytest.fixture
def collector():
    session = MagicMock()
    rds_client = MagicMock()
    cw_client = MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        rds_client if svc == "rds" else cw_client
    )
    c = RDSCollector(session, "eu-west-1", "TT-0001")
    c._rds = rds_client
    c._cw = cw_client
    return c, rds_client, cw_client


class TestRDSCollector:
    def test_collect_returns_inventory_record(self, collector):
        c, rds, cw = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = [r for r in records if r.metric_name == "db_instance_status"]
        assert len(inv) == 1
        assert inv[0].metric_value == "available"
        assert inv[0].resource_id == "mydb"

    def test_unavailable_instance_no_cw_metrics(self, collector):
        c, rds, cw = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance(status="stopped")]}
        ]
        records = c.collect()
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_storage_used_percent_derived_metric(self, collector):
        c, rds, cw = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance(allocated_gb=100)]}
        ]
        # FreeStorageSpace = 10GB (10% free → 90% used)
        free_bytes = 10 * 1024 ** 3

        def cw_side_effect(**kwargs):
            if kwargs["MetricName"] == "FreeStorageSpace":
                return {"Datapoints": [
                    {"Timestamp": datetime.now(timezone.utc), "Average": float(free_bytes)}
                ]}
            return {"Datapoints": []}

        cw.get_metric_statistics.side_effect = cw_side_effect
        records = c.collect()
        pct_records = [r for r in records if r.metric_name == "storage_used_percent"]
        assert len(pct_records) == 1
        assert abs(pct_records[0].metric_value - 90.0) < 0.1

    def test_storage_warning_flag_set_above_90_percent(self, collector):
        c, rds, cw = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance(allocated_gb=100)]}
        ]
        free_bytes = 5 * 1024 ** 3  # 5% free → 95% used

        def cw_side_effect(**kwargs):
            if kwargs["MetricName"] == "FreeStorageSpace":
                return {"Datapoints": [
                    {"Timestamp": datetime.now(timezone.utc), "Average": float(free_bytes)}
                ]}
            return {"Datapoints": []}

        cw.get_metric_statistics.side_effect = cw_side_effect
        records = c.collect()
        pct = [r for r in records if r.metric_name == "storage_used_percent"][0]
        assert pct.dimensions.get("storage_warning") == "True"

    def test_no_instances_returns_empty(self, collector):
        c, rds, cw = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": []}
        ]
        assert c.collect() == []

    def test_dimensions_include_engine_and_class(self, collector):
        c, rds, cw = collector
        rds.get_paginator.return_value.paginate.return_value = [
            {"DBInstances": [make_db_instance()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = records[0]
        assert inv.dimensions["engine"] == "postgres"
        assert inv.dimensions["instance_class"] == "db.t3.medium"
        assert inv.dimensions["multi_az"] == "True"
