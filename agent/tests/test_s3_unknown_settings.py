"""Denied S3 settings must remain unknown, not become failed controls."""
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointResolutionError

from collectors.s3 import S3Collector


def collect_with_failure(operation, error, response=None):
    s3, cw, session = MagicMock(), MagicMock(), MagicMock()
    session.client.side_effect = lambda service, **kwargs: s3 if service == "s3" else cw
    s3.list_buckets.return_value = {"Buckets": [{"Name": "review-fixture"}]}
    s3.get_bucket_location.return_value = {"LocationConstraint": "eu-west-2"}
    s3.get_bucket_versioning.return_value = {"Status": "Enabled"}
    s3.get_bucket_encryption.return_value = {
        "ServerSideEncryptionConfiguration": {"Rules": [
            {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
        ]}
    }
    s3.get_public_access_block.return_value = {"PublicAccessBlockConfiguration": {
        key: True for key in ("BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")
    }}
    cw.get_metric_statistics.return_value = {"Datapoints": []}
    if response is not None:
        getattr(s3, operation).return_value = response
    getattr(s3, operation).side_effect = error
    return S3Collector(session, "global", "TT-REVIEW").collect()[0].dimensions


@pytest.mark.parametrize("operation,field", [
    ("get_bucket_encryption", "encryption_enabled"),
    ("get_bucket_versioning", "versioning_enabled"),
])
@pytest.mark.parametrize("code", ["AccessDenied", "AccessDeniedException", "SlowDown"])
def test_unreadable_settings_are_not_reported_as_disabled(operation, field, code):
    error = ClientError({"Error": {"Code": code}}, operation)
    result = collect_with_failure(operation, error)
    assert field not in result
    if field == "encryption_enabled":
        assert "encryption_algorithm" not in result


@pytest.mark.parametrize("operation,field", [
    ("get_bucket_encryption", "encryption_enabled"),
    ("get_bucket_versioning", "versioning_enabled"),
])
def test_endpoint_failure_does_not_invent_a_setting(operation, field):
    assert field not in collect_with_failure(operation, EndpointResolutionError(msg="unavailable"))


def test_readable_empty_versioning_response_is_disabled():
    # No Status after a successful AWS read means versioning was never enabled.
    assert collect_with_failure("get_bucket_versioning", None, {})["versioning_enabled"] == "False"
