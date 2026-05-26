"""Unit tests for the ECSCollector."""
import pytest
from unittest.mock import MagicMock, call
from botocore.exceptions import ClientError
from collectors.ecs import ECSCollector


def make_cluster(name="my-cluster", status="ACTIVE"):
    return {
        "clusterArn": f"arn:aws:ecs:eu-west-1:123:cluster/{name}",
        "clusterName": name,
        "status": status,
        "runningTasksCount": 3,
        "pendingTasksCount": 0,
        "activeServicesCount": 2,
    }


def make_service(cluster_name="my-cluster", svc_name="api", status="ACTIVE"):
    return {
        "serviceName": svc_name,
        "serviceArn": f"arn:aws:ecs:eu-west-1:123:service/{cluster_name}/{svc_name}",
        "status": status,
        "launchType": "FARGATE",
        "desiredCount": 2,
        "runningCount": 2,
        "pendingCount": 0,
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ecs_client = MagicMock()
    cw_client = MagicMock()
    session.client.side_effect = lambda svc, **kw: (
        ecs_client if svc == "ecs" else cw_client
    )
    c = ECSCollector(session, "eu-west-1", "TT-0001")
    c._ecs = ecs_client
    c._cw = cw_client
    return c, ecs_client, cw_client


class TestECSCollector:
    def test_service_name_is_ecs(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "ecs"

    def test_no_clusters_returns_empty(self, collector):
        c, ecs, _ = collector
        ecs.list_clusters.return_value = {"clusterArns": []}
        assert c.collect() == []

    def test_cluster_inventory_record_emitted(self, collector):
        c, ecs, cw = collector
        cluster = make_cluster()
        ecs.list_clusters.return_value = {"clusterArns": [cluster["clusterArn"]]}
        ecs.describe_clusters.return_value = {"clusters": [cluster]}
        ecs.get_paginator.return_value.paginate.return_value = [{"serviceArns": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        inv = [r for r in records if r.metric_name == "cluster_status"]
        assert len(inv) == 1
        assert inv[0].metric_value == "ACTIVE"
        assert inv[0].resource_id == "my-cluster"

    def test_cluster_dimensions_include_task_counts(self, collector):
        c, ecs, cw = collector
        cluster = make_cluster()
        ecs.list_clusters.return_value = {"clusterArns": [cluster["clusterArn"]]}
        ecs.describe_clusters.return_value = {"clusters": [cluster]}
        ecs.get_paginator.return_value.paginate.return_value = [{"serviceArns": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        inv = records[0]
        assert inv.dimensions["running_tasks"] == 3
        assert inv.dimensions["active_services"] == 2

    def test_inactive_cluster_skips_services(self, collector):
        c, ecs, cw = collector
        cluster = make_cluster(status="INACTIVE")
        ecs.list_clusters.return_value = {"clusterArns": [cluster["clusterArn"]]}
        ecs.describe_clusters.return_value = {"clusters": [cluster]}

        records = c.collect()
        assert len(records) == 1
        ecs.get_paginator.assert_not_called()

    def test_service_status_and_task_count_records(self, collector):
        c, ecs, cw = collector
        cluster = make_cluster()
        svc = make_service()
        svc_arn = svc["serviceArn"]

        ecs.list_clusters.return_value = {"clusterArns": [cluster["clusterArn"]]}
        ecs.describe_clusters.return_value = {"clusters": [cluster]}
        ecs.get_paginator.return_value.paginate.return_value = [{"serviceArns": [svc_arn]}]
        ecs.describe_services.return_value = {"services": [svc]}
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        status_recs = [r for r in records if r.metric_name == "service_status"]
        task_recs = [r for r in records if r.metric_name == "running_task_count"]
        assert len(status_recs) == 1
        assert status_recs[0].metric_value == "ACTIVE"
        assert len(task_recs) == 1
        assert task_recs[0].metric_value == 2

    def test_service_cw_cpu_emitted(self, collector):
        from datetime import datetime, timezone
        c, ecs, cw = collector
        cluster = make_cluster()
        svc = make_service()

        ecs.list_clusters.return_value = {"clusterArns": [cluster["clusterArn"]]}
        ecs.describe_clusters.return_value = {"clusters": [cluster]}
        ecs.get_paginator.return_value.paginate.return_value = [{"serviceArns": [svc["serviceArn"]]}]
        ecs.describe_services.return_value = {"services": [svc]}
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 42.5}]
        }

        records = c.collect()
        cpu = [r for r in records if r.metric_name == "cpu_utilization_percent"]
        assert len(cpu) == 1
        assert cpu[0].metric_value == 42.5

    def test_client_error_returns_empty(self, collector):
        c, ecs, _ = collector
        ecs.list_clusters.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListClusters",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, ecs, cw = collector
        cluster = make_cluster()
        ecs.list_clusters.return_value = {"clusterArns": [cluster["clusterArn"]]}
        ecs.describe_clusters.return_value = {"clusters": [cluster]}
        ecs.get_paginator.return_value.paginate.return_value = [{"serviceArns": []}]
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
