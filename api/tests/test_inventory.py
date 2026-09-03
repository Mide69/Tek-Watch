"""What a customer has — the question the dashboard asks and nothing answered.

The overview counted distinct resource_ids from
`get_resources_by_service(customer, "ec2", "5m")`. An account with no EC2
therefore reported zero resources while its agent was reporting fifty across
eighteen regions, and the region panel beside it was three hardcoded regions
split 76/17/7, computed from that same broken total rather than measured.

These tests cover the fold that replaced it, and the cost queries that were
counting one day once per collection cycle.
"""
from decimal import Decimal

import pytest
from unittest.mock import MagicMock, patch

from services.inventory_view import dim, flag, num, text
from services.timestream import TimestreamQueryService


@pytest.fixture
def svc():
    with patch("services.timestream.boto3") as mock_boto3, \
         patch("services.timestream.load_config") as mock_config:
        mock_config.return_value = MagicMock(
            aws_region="eu-west-2",
            dynamodb_metrics_table="tek_watch_metrics",
            dynamodb_events_table="tek_watch_events",
        )
        metrics_table = MagicMock()
        events_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.side_effect = lambda name: {
            "tek_watch_metrics": metrics_table,
            "tek_watch_events": events_table,
        }[name]
        mock_boto3.resource.return_value = mock_dynamodb
        return TimestreamQueryService(), metrics_table, events_table


def _metric(service, resource_id, metric_name, value, region="eu-west-2",
            time="2026-09-03T09:50:00+00:00", **extra):
    row = {
        "service": service,
        "resource_id": resource_id,
        "resource_name": resource_id,
        "region": region,
        "time": time,
        "metric_name": metric_name,
        "value": Decimal(str(value)),
    }
    row.update(extra)
    return row


class TestResourceInventory:
    def _rows(self):
        return [
            _metric("s3", "bucket-a", "number_of_objects", 12, "eu-west-2"),
            _metric("s3", "bucket-b", "number_of_objects", 4, "us-east-1"),
            _metric("iam", "iam", "total_users", 3, "global"),
        ]

    def test_counts_every_service_not_just_ec2(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": self._rows()}
        assert s.get_resource_inventory("TT-0001")["total"] == 3

    def test_repeated_collections_count_once(self, svc):
        s, metrics_table, _ = svc
        # The agent re-reports every resource on every cycle.
        metrics_table.query.return_value = {"Items": self._rows() + self._rows()}
        assert s.get_resource_inventory("TT-0001")["total"] == 3

    def test_region_breakdown_is_measured(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": self._rows()}
        by_region = s.get_resource_inventory("TT-0001")["by_region"]
        assert {r["region"]: r["count"] for r in by_region} == {
            "eu-west-2": 1, "us-east-1": 1, "global": 1,
        }

    def test_same_resource_id_in_two_services_counts_twice(self, svc):
        s, metrics_table, _ = svc
        # The cost collector reports the customer id as a resource, so a
        # resource_id is only unique within its service.
        metrics_table.query.return_value = {"Items": [
            _metric("cost_explorer", "TT-0001", "daily_blended_cost", 1, "global"),
            _metric("iam", "TT-0001", "total_users", 3, "global"),
        ]}
        assert s.get_resource_inventory("TT-0001")["total"] == 2

    def test_empty_account_reports_nothing_rather_than_failing(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": []}
        assert s.get_resource_inventory("TT-0001") == {
            "total": 0, "by_region": [], "by_service": [],
        }

    def test_rows_without_a_resource_id_are_skipped(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": [
            {"service": "s3", "region": "eu-west-2", "metric_name": "x",
             "time": "2026-09-03T09:50:00+00:00", "value": Decimal("1")},
        ]}
        assert s.get_resource_inventory("TT-0001")["total"] == 0


class TestServiceInventory:
    """A resource is every row about it, folded together, from both tables."""

    def test_merges_events_and_metrics_for_one_resource(self, svc):
        s, metrics_table, events_table = svc
        # A bucket's state is a string and lives in events; its size is a
        # number and lives in metrics. Reading only events, as every resource
        # router did, meant the numbers were never in the response at all.
        events_table.query.return_value = {"Items": [{
            "resource_id": "bucket-a", "resource_name": "bucket-a", "service": "s3",
            "region": "eu-west-2", "time": "2026-09-03T09:50:00+00:00",
            "metric_name": "bucket_state", "value": "active",
            "dimensions": {"encryption_enabled": "True"},
        }]}
        metrics_table.query.return_value = {"Items": [
            _metric("s3", "bucket-a", "bucket_size_bytes", 2048),
        ]}

        inventory = s.get_service_inventory("TT-0001", "s3")
        assert len(inventory) == 1
        bucket = inventory[0]
        assert bucket["metrics"]["bucket_size_bytes"] == 2048.0
        assert bucket["metrics"]["bucket_state"] == "active"
        assert bucket["dimensions"]["encryption_enabled"] == "True"

    def test_newest_reading_wins(self, svc):
        s, metrics_table, events_table = svc
        events_table.query.return_value = {"Items": []}
        metrics_table.query.return_value = {"Items": [
            _metric("s3", "b", "number_of_objects", 1, time="2026-09-03T09:00:00+00:00"),
            _metric("s3", "b", "number_of_objects", 9, time="2026-09-03T09:55:00+00:00"),
        ]}
        inventory = s.get_service_inventory("TT-0001", "s3")
        assert inventory[0]["metrics"]["number_of_objects"] == 9.0
        assert inventory[0]["last_seen"] == "2026-09-03T09:55:00+00:00"

    def test_other_services_are_excluded(self, svc):
        s, metrics_table, events_table = svc
        events_table.query.return_value = {"Items": []}
        metrics_table.query.return_value = {"Items": [
            _metric("s3", "b", "number_of_objects", 1),
            _metric("iam", "iam", "total_users", 3, "global"),
        ]}
        assert [r["resource_id"] for r in s.get_service_inventory("TT-0001", "s3")] == ["b"]

    def test_string_values_survive_the_fold(self, svc):
        s, metrics_table, events_table = svc
        events_table.query.return_value = {"Items": [{
            "resource_id": "vpc-1", "resource_name": "prod", "service": "vpc",
            "region": "eu-west-2", "time": "2026-09-03T09:50:00+00:00",
            "metric_name": "vpc_state", "value": "available",
        }]}
        metrics_table.query.return_value = {"Items": []}
        assert s.get_service_inventory("TT-0001", "vpc")[0]["metrics"]["vpc_state"] == "available"


class TestCostDeduplication:
    """The agent re-reports the running daily total on every collection."""

    def test_one_row_per_calendar_day(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": [
            _metric("cost_explorer", "TT-0001", "daily_blended_cost", "0.0007",
                    time=f"2026-09-03T09:{m:02d}:00+00:00")
            for m in (14, 20, 25, 30, 35)
        ]}
        assert len(s.get_daily_costs("TT-0001")) == 1

    def test_month_to_date_is_not_multiplied_by_collection_frequency(self, svc):
        s, metrics_table, _ = svc
        # Two days, each reported three times. The total is the two days, not six.
        items = [
            _metric("cost_explorer", "TT-0001", "daily_blended_cost", value,
                    time=f"2026-09-{day}T09:{m}:00+00:00")
            for day, value in (("02", "1.00"), ("03", "2.00"))
            for m in (10, 20, 30)
        ]
        metrics_table.query.return_value = {"Items": items}
        assert sum(r["cost"] for r in s.get_daily_costs("TT-0001")) == 3.00

    def test_last_reading_of_the_day_wins(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": [
            _metric("cost_explorer", "TT-0001", "daily_blended_cost", "1.00",
                    time="2026-09-03T09:10:00+00:00"),
            _metric("cost_explorer", "TT-0001", "daily_blended_cost", "4.00",
                    time="2026-09-03T23:50:00+00:00"),
        ]}
        assert s.get_daily_costs("TT-0001")[0]["cost"] == 4.00

    def test_service_breakdown_lists_each_service_once(self, svc):
        s, metrics_table, _ = svc
        metrics_table.query.return_value = {"Items": [
            _metric("cost_explorer", "s3", "mtd_blended_cost", "0.0016",
                    resource_name="amazon_simple_storage_service",
                    time=f"2026-09-03T09:{m:02d}:00+00:00")
            for m in (14, 20, 25)
        ]}
        breakdown = s.get_service_costs("TT-0001")
        assert len(breakdown) == 1
        assert breakdown[0]["aws_service"] == "amazon_simple_storage_service"


class TestInventoryViewHelpers:
    """Absent and "we checked, the answer is no" are different answers."""

    def test_false_dimension_reads_as_false(self):
        # Dimensions are strings by the time they reach DynamoDB, so "False"
        # is a non-empty string and truthy in both Python and JavaScript. Read
        # naively, every bucket in an account looks encrypted and versioned.
        assert flag({"dimensions": {"encryption_enabled": "False"}}, "encryption_enabled") is False
        assert flag({"dimensions": {"encryption_enabled": "True"}}, "encryption_enabled") is True

    def test_uncollected_dimension_is_none_not_false(self):
        # The storage page labels a bucket Public when public_access_blocked is
        # falsey. A missing field returning False labels the whole account.
        assert flag({"dimensions": {}}, "public_access_blocked") is None
        assert flag({}, "public_access_blocked") is None

    def test_flag_accepts_the_words_collectors_use(self):
        assert flag({"dimensions": {"v": "enabled"}}, "v") is True
        assert flag({"dimensions": {"v": "disabled"}}, "v") is False
        assert flag({"dimensions": {"v": ""}}, "v") is None

    def test_uncollected_metric_is_none_not_zero(self):
        assert num({"metrics": {}}, "bucket_size_bytes") is None
        assert num({"metrics": {"bucket_size_bytes": 4}}, "bucket_size_bytes") == 4.0

    def test_non_numeric_metric_does_not_raise(self):
        assert num({"metrics": {"state": "active"}}, "state") is None

    def test_text_reads_event_values(self):
        assert text({"metrics": {"vpc_state": "available"}}, "vpc_state") == "available"
        assert text({"metrics": {}}, "vpc_state", "unknown") == "unknown"

    def test_dim_defaults_to_empty_string(self):
        assert dim({}, "domain") == ""
        assert dim({"dimensions": {"domain": "example.com"}}, "domain") == "example.com"
