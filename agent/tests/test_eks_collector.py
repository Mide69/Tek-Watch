"""Unit tests for the EKSCollector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.eks import EKSCollector


def make_cluster_detail(name="prod-cluster", status="ACTIVE", version="1.29"):
    return {
        "cluster": {
            "name": name,
            "status": status,
            "version": version,
            "endpoint": "https://abc.gr7.eu-west-1.eks.amazonaws.com",
            "roleArn": "arn:aws:iam::123:role/eks-role",
        }
    }


def make_nodegroup_detail(name="workers", status="ACTIVE"):
    return {
        "nodegroup": {
            "nodegroupName": name,
            "status": status,
            "instanceTypes": ["m5.large"],
            "scalingConfig": {"desiredSize": 3, "minSize": 1, "maxSize": 5},
        }
    }


def _setup_single_cluster(eks, cw, cluster_name="prod-cluster", nodegroups=None):
    """Wire paginate side_effect for list_clusters then list_nodegroups calls."""
    nodegroups = nodegroups or []
    eks.get_paginator.return_value.paginate.side_effect = [
        [{"clusters": [cluster_name]}],
        [{"nodegroups": nodegroups}],
    ]
    eks.describe_cluster.return_value = make_cluster_detail(name=cluster_name)
    cw.get_metric_statistics.return_value = {"Datapoints": []}


@pytest.fixture
def collector():
    session = MagicMock()
    eks = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: eks if svc == "eks" else cw
    c = EKSCollector(session, "eu-west-1", "TT-0001")
    c._eks = eks
    c._cw = cw
    return c, eks, cw


class TestEKSCollector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "eks"

    def test_no_clusters_returns_empty(self, collector):
        c, eks, _ = collector
        eks.get_paginator.return_value.paginate.return_value = [{"clusters": []}]
        assert c.collect() == []

    def test_cluster_status_emitted(self, collector):
        c, eks, cw = collector
        _setup_single_cluster(eks, cw)

        records = c.collect()
        cluster_recs = [r for r in records if r.metric_name == "cluster_status"]
        assert len(cluster_recs) == 1
        assert cluster_recs[0].metric_value == "ACTIVE"
        assert cluster_recs[0].resource_id == "prod-cluster"

    def test_inactive_cluster_skips_nodegroups_and_cw(self, collector):
        c, eks, cw = collector
        eks.get_paginator.return_value.paginate.return_value = [{"clusters": ["idle-cluster"]}]
        eks.describe_cluster.return_value = make_cluster_detail(status="DELETING")

        records = c.collect()
        assert len(records) == 1
        assert records[0].metric_name == "cluster_status"
        cw.get_metric_statistics.assert_not_called()

    def test_node_group_status_emitted(self, collector):
        c, eks, cw = collector
        _setup_single_cluster(eks, cw, nodegroups=["workers"])
        eks.describe_nodegroup.return_value = make_nodegroup_detail()

        records = c.collect()
        ng_recs = [r for r in records if r.metric_name == "node_group_status"]
        assert len(ng_recs) == 1
        assert ng_recs[0].metric_value == "ACTIVE"

    def test_desired_node_count_emitted(self, collector):
        c, eks, cw = collector
        _setup_single_cluster(eks, cw, nodegroups=["workers"])
        eks.describe_nodegroup.return_value = make_nodegroup_detail()

        records = c.collect()
        desired_recs = [r for r in records if r.metric_name == "desired_node_count"]
        assert len(desired_recs) == 1
        assert desired_recs[0].metric_value == 3

    def test_cw_container_insights_emitted_when_data(self, collector):
        c, eks, cw = collector
        _setup_single_cluster(eks, cw)
        cw.get_metric_statistics.return_value = {
            "Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 55.0}]
        }

        records = c.collect()
        cpu_recs = [r for r in records if r.metric_name == "node_cpu_utilization_percent"]
        assert len(cpu_recs) == 1
        assert cpu_recs[0].metric_value == 55.0

    def test_client_error_returns_empty(self, collector):
        c, eks, _ = collector
        eks.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListClusters",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, eks, cw = collector
        _setup_single_cluster(eks, cw)

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
