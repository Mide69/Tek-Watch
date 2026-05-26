"""Unit tests for the ElastiCacheCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.elasticache import ElastiCacheCollector


def make_cluster(cluster_id="redis-prod", engine="redis", status="available"):
    return {
        "CacheClusterId": cluster_id,
        "Engine": engine,
        "EngineVersion": "7.0.7",
        "CacheClusterStatus": status,
        "CacheNodeType": "cache.r7g.large",
        "NumCacheNodes": 1,
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ec = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        ec if svc == "elasticache" else cw
    )
    c = ElastiCacheCollector(session, "eu-west-1", "TT-0001")
    c._ec = ec
    c._cw = cw
    return c, ec, cw


class TestElastiCacheCollector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "elasticache"

    def test_no_clusters_returns_empty(self, collector):
        c, ec, _ = collector
        ec.get_paginator.return_value.paginate.return_value = [{"CacheClusters": []}]
        assert c.collect() == []

    def test_inventory_record_emitted(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        inv = [r for r in records if r.metric_name == "cluster_status"]
        assert len(inv) == 1
        assert inv[0].metric_value == "available"
        assert inv[0].resource_id == "redis-prod"

    def test_unavailable_cluster_skips_cw(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster(status="creating")]}
        ]
        records = c.collect()
        assert len(records) == 1
        cw.get_metric_statistics.assert_not_called()

    def test_cw_cpu_metric_emitted(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster()]}
        ]
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 25.5}]
        }

        records = c.collect()
        cpu = [r for r in records if r.metric_name == "cpu_utilization_percent"]
        assert len(cpu) == 1
        assert cpu[0].metric_value == 25.5

    def test_cache_hit_ratio_computed(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster()]}
        ]
        ts = datetime.now(timezone.utc)

        def cw_response(Namespace, MetricName, **kw):
            if MetricName == "CacheHits":
                return {"Datapoints": [{"Timestamp": ts, "Average": 80.0}]}
            if MetricName == "CacheMisses":
                return {"Datapoints": [{"Timestamp": ts, "Average": 20.0}]}
            return {"Datapoints": []}

        cw.get_metric_statistics.side_effect = cw_response

        records = c.collect()
        ratio = next((r for r in records if r.metric_name == "cache_hit_ratio_percent"), None)
        assert ratio is not None
        assert ratio.metric_value == 80.0

    def test_cache_hit_ratio_skipped_when_no_data(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        ratio = [r for r in records if r.metric_name == "cache_hit_ratio_percent"]
        assert ratio == []

    def test_client_error_returns_empty(self, collector):
        c, ec, _ = collector
        ec.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "DescribeCacheClusters",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)

    def test_dimensions_include_engine_and_node_type(self, collector):
        c, ec, cw = collector
        ec.get_paginator.return_value.paginate.return_value = [
            {"CacheClusters": [make_cluster()]}
        ]
        cw.get_metric_statistics.return_value = {"Datapoints": []}
        records = c.collect()
        inv = records[0]
        assert inv.dimensions["engine"] == "redis"
        assert inv.dimensions["node_type"] == "cache.r7g.large"
