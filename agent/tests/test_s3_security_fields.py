"""S3 facts the dashboard shows but nothing collected.

The storage page has a Public column and names the encryption algorithm beside
a padlock. The collector reported neither: encryption was a bare boolean, and
public access was not looked at all, so every bucket in an account was about
to be labelled Public on the strength of a field that did not exist.
"""
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from collectors.s3 import S3Collector


def make_bucket(name="my-data-bucket"):
    return {"Name": name}


def _client_error(code):
    return ClientError({"Error": {"Code": code}}, "op")


@pytest.fixture
def collector():
    session = MagicMock()
    s3 = MagicMock()
    cw = MagicMock()
    session.client.side_effect = lambda svc, **kw: s3 if svc == "s3" else cw
    c = S3Collector(session, "global", "TT-0001")
    c._s3 = s3
    c._cw = cw
    s3.list_buckets.return_value = {"Buckets": [make_bucket()]}
    s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    cw.get_metric_statistics.return_value = {"Datapoints": []}
    return c, s3, cw


def _dims(records):
    return records[0].dimensions


class TestEncryptionAlgorithm:
    def test_algorithm_is_reported(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
            }
        }
        s3.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": {}}

        dims = _dims(c.collect())
        assert dims["encryption_enabled"] == "True"
        assert dims["encryption_algorithm"] == "aws:kms"

    def test_unencrypted_bucket_reports_no_algorithm(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.side_effect = _client_error(
            "ServerSideEncryptionConfigurationNotFoundError"
        )
        s3.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": {}}

        dims = _dims(c.collect())
        assert dims["encryption_enabled"] == "False"
        assert dims["encryption_algorithm"] == ""

    def test_permission_error_does_not_claim_encryption(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.side_effect = _client_error("AccessDenied")
        s3.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": {}}

        dims = _dims(c.collect())
        assert "encryption_enabled" not in dims
        assert "encryption_algorithm" not in dims


class TestPublicAccessBlock:
    def _block(self, **overrides):
        cfg = {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
        cfg.update(overrides)
        return {"PublicAccessBlockConfiguration": cfg}

    def test_fully_blocked_bucket(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.return_value = {}
        s3.get_public_access_block.return_value = self._block()
        assert _dims(c.collect())["public_access_blocked"] == "True"

    def test_partially_blocked_bucket_is_not_blocked(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.return_value = {}
        s3.get_public_access_block.return_value = self._block(RestrictPublicBuckets=False)
        # Three of the four settings on is not "blocked". Reporting it as
        # blocked is the failure mode that matters here.
        assert _dims(c.collect())["public_access_blocked"] == "False"

    def test_no_configuration_means_not_blocked(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.return_value = {}
        s3.get_public_access_block.side_effect = _client_error(
            "NoSuchPublicAccessBlockConfiguration"
        )
        assert _dims(c.collect())["public_access_blocked"] == "False"

    def test_unreadable_setting_is_left_unknown(self, collector):
        c, s3, cw = collector
        s3.get_bucket_encryption.return_value = {}
        s3.get_public_access_block.side_effect = _client_error("AccessDenied")
        # Neither guess is safe: claiming a bucket is blocked when it is not is
        # dangerous, and claiming it is public when it is not trains people to
        # ignore the warning. Absent, so the page can say so.
        assert "public_access_blocked" not in _dims(c.collect())
