"""Unit tests for the CloudTrailCollector."""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.cloudtrail import CloudTrailCollector


def make_event(event_name="CreateUser", username="alice", event_id="evt-001"):
    return {
        "EventId": event_id,
        "EventName": event_name,
        "EventTime": datetime(2026, 5, 25, 10, 0, tzinfo=timezone.utc),
        "Username": username,
        "Resources": [{"ResourceName": "test-resource"}],
        "CloudTrailEvent": json.dumps({"sourceIPAddress": "1.2.3.4"}),
    }


@pytest.fixture
def collector():
    session = MagicMock()
    ct = MagicMock()
    session.client.return_value = ct
    ct.describe_trails.return_value = {"trailList": []}
    c = CloudTrailCollector(session, "eu-west-1", "TT-0001")
    c._ct = ct
    return c, ct


def trail(name):
    return {"Name": name, "TrailARN": f"arn:aws:cloudtrail:eu-west-1:111111111111:trail/{name}"}


class TestCloudTrailCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "cloudtrail"

    def test_no_events_emits_summary_zero(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]

        records = c.collect()
        summary = next(r for r in records if r.metric_name == "high_risk_events_24h")
        assert summary.metric_value == 0

    def test_high_risk_event_recorded(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [
            {"Events": [make_event("CreateUser")]}
        ]
        records = c.collect()
        event_recs = [r for r in records if r.metric_name == "high_risk_event"]
        assert len(event_recs) == 1
        assert event_recs[0].metric_value == "CreateUser"

    def test_non_high_risk_event_ignored(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [
            {"Events": [make_event("DescribeInstances")]}
        ]
        records = c.collect()
        event_recs = [r for r in records if r.metric_name == "high_risk_event"]
        assert event_recs == []

    def test_summary_count_matches_events(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [
            {"Events": [
                make_event("CreateUser", event_id="e1"),
                make_event("DeleteUser", event_id="e2"),
                make_event("CreateAccessKey", event_id="e3"),
            ]}
        ]
        records = c.collect()
        summary = next(r for r in records if r.metric_name == "high_risk_events_24h")
        assert summary.metric_value == 3

    def test_event_dimensions_include_username(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [
            {"Events": [make_event("CreateUser", username="bob")]}
        ]
        records = c.collect()
        event_rec = next(r for r in records if r.metric_name == "high_risk_event")
        assert event_rec.dimensions["username"] == "bob"

    # Event lookup failing must not stop the trail status check, and vice
    # versa: they answer different questions.
    def test_access_denied_emits_no_events(self, collector):
        c, ct = collector
        ct.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "LookupEvents",
        )
        assert [r.metric_name for r in c.collect()] == ["trails_logging_count"]

    def test_endpoint_error_emits_no_events(self, collector):
        c, ct = collector
        ct.get_paginator.side_effect = EndpointResolutionError(msg="endpoint not available")
        assert [r.metric_name for r in c.collect()] == ["trails_logging_count"]

    def test_delete_public_access_block_is_high_risk(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [
            {"Events": [make_event("DeleteBucketPublicAccessBlock")]}
        ]
        records = c.collect()
        assert any(r.metric_value == "DeleteBucketPublicAccessBlock" for r in records)

    def test_counts_only_trails_that_are_logging(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        ct.describe_trails.return_value = {"trailList": [trail("org"), trail("old")]}
        ct.get_trail_status.side_effect = lambda Name: {"IsLogging": Name.endswith("/org")}

        rec = next(r for r in c.collect() if r.metric_name == "trails_logging_count")
        assert rec.metric_value == 1
        assert rec.dimensions["trails_total"] == "2"
        ct.describe_trails.assert_called_once_with(includeShadowTrails=True)

    def test_no_trails_reports_zero_logging(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        rec = next(r for r in c.collect() if r.metric_name == "trails_logging_count")
        assert rec.metric_value == 0

    def test_unreadable_trail_status_is_unknown_not_zero(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        ct.describe_trails.return_value = {"trailList": [trail("org")]}
        ct.get_trail_status.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "GetTrailStatus",
        )
        assert all(r.metric_name != "trails_logging_count" for r in c.collect())

    def test_describe_trails_denied_is_unknown(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        ct.describe_trails.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "DescribeTrails",
        )
        assert all(r.metric_name != "trails_logging_count" for r in c.collect())

    def test_customer_id_propagated(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)


class TestLookupCost:
    """LookupEvents allows two calls a second. Paging through every read made
    each run slower than the last, because the agent's own reads are events."""

    def test_asks_cloudtrail_for_write_events_only(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        c.collect()
        kwargs = ct.get_paginator.return_value.paginate.call_args.kwargs
        assert kwargs["LookupAttributes"] == [{"AttributeKey": "ReadOnly", "AttributeValue": "false"}]

    def test_stops_paging_at_the_cap(self, collector):
        from collectors import cloudtrail
        c, ct = collector
        seen = []

        def pages():
            for i in range(cloudtrail.MAX_PAGES + 30):
                seen.append(i)
                yield {"Events": [make_event("DescribeInstances", event_id=f"e{i}")]}

        ct.get_paginator.return_value.paginate.return_value = pages()
        records = c.collect()
        assert len(seen) == cloudtrail.MAX_PAGES + 1
        assert any(r.metric_name == "high_risk_events_24h" for r in records)
