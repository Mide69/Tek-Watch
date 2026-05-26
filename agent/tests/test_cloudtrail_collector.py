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
    c = CloudTrailCollector(session, "eu-west-1", "TT-0001")
    c._ct = ct
    return c, ct


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

    def test_access_denied_returns_empty(self, collector):
        c, ct = collector
        ct.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "LookupEvents",
        )
        assert c.collect() == []

    def test_endpoint_error_returns_empty(self, collector):
        c, ct = collector
        ct.get_paginator.side_effect = EndpointResolutionError(msg="endpoint not available")
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, ct = collector
        ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
