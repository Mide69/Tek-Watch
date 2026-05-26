"""Unit tests for the S3Collector."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.s3 import S3Collector


def make_bucket(name="my-data-bucket"):
    return {"Name": name}


@pytest.fixture
def collector():
    session = MagicMock()
    s3 = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: s3 if svc == "s3" else cw
    c = S3Collector(session, "global", "TT-0001")
    c._s3 = s3
    c._cw = cw
    return c, s3, cw


class TestS3Collector:
    def test_service_name(self, collector):
        c, _, _ = collector
        assert c.SERVICE_NAME == "s3"

    def test_region_is_always_global(self, collector):
        c, _, _ = collector
        assert c.region == "global"

    def test_no_buckets_returns_empty(self, collector):
        c, s3, _ = collector
        s3.list_buckets.return_value = {"Buckets": []}
        assert c.collect() == []

    def test_bucket_state_emitted(self, collector):
        c, s3, cw = collector
        s3.list_buckets.return_value = {"Buckets": [make_bucket()]}
        s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
        s3.get_bucket_encryption.return_value = {}
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_recs = [r for r in records if r.metric_name == "bucket_state"]
        assert len(state_recs) == 1
        assert state_recs[0].metric_value == "active"
        assert state_recs[0].resource_id == "my-data-bucket"

    def test_versioning_in_dimensions(self, collector):
        c, s3, cw = collector
        s3.list_buckets.return_value = {"Buckets": [make_bucket()]}
        s3.get_bucket_location.return_value = {"LocationConstraint": None}
        s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
        s3.get_bucket_encryption.return_value = {}
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        state_rec = next(r for r in records if r.metric_name == "bucket_state")
        assert state_rec.dimensions["versioning_enabled"] == "True"

    def test_bucket_size_emitted_when_cw_data(self, collector):
        c, s3, cw = collector
        s3.list_buckets.return_value = {"Buckets": [make_bucket()]}
        s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        s3.get_bucket_versioning.return_value = {}
        s3.get_bucket_encryption.return_value = {}

        def cw_response(Namespace, MetricName, **kw):
            if MetricName == "BucketSizeBytes":
                return {"Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 5_000_000.0}]}
            return {"Datapoints": []}

        cw.get_metric_statistics.side_effect = cw_response

        records = c.collect()
        size_recs = [r for r in records if r.metric_name == "bucket_size_bytes"]
        assert len(size_recs) == 1
        assert size_recs[0].metric_value == 5_000_000

    def test_object_count_emitted_when_cw_data(self, collector):
        c, s3, cw = collector
        s3.list_buckets.return_value = {"Buckets": [make_bucket()]}
        s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        s3.get_bucket_versioning.return_value = {}
        s3.get_bucket_encryption.return_value = {}

        def cw_response(Namespace, MetricName, **kw):
            if MetricName == "NumberOfObjects":
                return {"Datapoints": [{"Timestamp": datetime.now(timezone.utc), "Average": 1234.0}]}
            return {"Datapoints": []}

        cw.get_metric_statistics.side_effect = cw_response

        records = c.collect()
        obj_recs = [r for r in records if r.metric_name == "number_of_objects"]
        assert len(obj_recs) == 1
        assert obj_recs[0].metric_value == 1234

    def test_access_denied_returns_empty(self, collector):
        c, s3, _ = collector
        s3.list_buckets.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListBuckets",
        )
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, s3, cw = collector
        s3.list_buckets.return_value = {"Buckets": [make_bucket()]}
        s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        s3.get_bucket_versioning.return_value = {}
        s3.get_bucket_encryption.return_value = {}
        cw.get_metric_statistics.return_value = {"Datapoints": []}

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
