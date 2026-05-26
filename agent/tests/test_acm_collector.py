"""Unit tests for the ACMCollector."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from botocore.exceptions import ClientError, EndpointResolutionError
from collectors.acm import ACMCollector


def make_cert_summary(arn="arn:aws:acm:eu-west-1:123:certificate/abc", domain="example.com"):
    return {"CertificateArn": arn, "DomainName": domain}


def make_cert_detail(status="ISSUED", days_from_now=90, cert_type="AMAZON_ISSUED"):
    expiry = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return {
        "Certificate": {
            "CertificateArn": "arn:aws:acm:eu-west-1:123:certificate/abc",
            "DomainName": "example.com",
            "Status": status,
            "Type": cert_type,
            "NotAfter": expiry,
        }
    }


@pytest.fixture
def collector():
    session = MagicMock()
    acm = MagicMock()
    session.client.return_value = acm
    c = ACMCollector(session, "eu-west-1", "TT-0001")
    c._acm = acm
    return c, acm


class TestACMCollector:
    def test_service_name(self, collector):
        c, _ = collector
        assert c.SERVICE_NAME == "acm"

    def test_no_certs_returns_empty(self, collector):
        c, acm = collector
        acm.get_paginator.return_value.paginate.return_value = [
            {"CertificateSummaryList": []}
        ]
        assert c.collect() == []

    def test_cert_records_emitted(self, collector):
        c, acm = collector
        acm.get_paginator.return_value.paginate.return_value = [
            {"CertificateSummaryList": [make_cert_summary()]}
        ]
        acm.describe_certificate.return_value = make_cert_detail()

        records = c.collect()
        metric_names = {r.metric_name for r in records}
        assert "days_until_expiry" in metric_names
        assert "certificate_status" in metric_names

    def test_expiring_cert_days_calculated(self, collector):
        c, acm = collector
        acm.get_paginator.return_value.paginate.return_value = [
            {"CertificateSummaryList": [make_cert_summary()]}
        ]
        acm.describe_certificate.return_value = make_cert_detail(days_from_now=30)

        records = c.collect()
        expiry_rec = next(r for r in records if r.metric_name == "days_until_expiry")
        assert 28 <= expiry_rec.metric_value <= 31

    def test_expired_cert_shows_zero_days(self, collector):
        c, acm = collector
        acm.get_paginator.return_value.paginate.return_value = [
            {"CertificateSummaryList": [make_cert_summary()]}
        ]
        acm.describe_certificate.return_value = make_cert_detail(days_from_now=-10)

        records = c.collect()
        expiry_rec = next(r for r in records if r.metric_name == "days_until_expiry")
        assert expiry_rec.metric_value == 0

    def test_cert_status_in_record(self, collector):
        c, acm = collector
        acm.get_paginator.return_value.paginate.return_value = [
            {"CertificateSummaryList": [make_cert_summary()]}
        ]
        acm.describe_certificate.return_value = make_cert_detail(status="PENDING_VALIDATION")

        records = c.collect()
        status_rec = next(r for r in records if r.metric_name == "certificate_status")
        assert status_rec.metric_value == "PENDING_VALIDATION"

    def test_access_denied_returns_empty(self, collector):
        c, acm = collector
        acm.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "ListCertificates",
        )
        assert c.collect() == []

    def test_endpoint_error_returns_empty(self, collector):
        c, acm = collector
        acm.get_paginator.side_effect = EndpointResolutionError(msg="endpoint not available")
        assert c.collect() == []

    def test_customer_id_propagated(self, collector):
        c, acm = collector
        acm.get_paginator.return_value.paginate.return_value = [
            {"CertificateSummaryList": [make_cert_summary()]}
        ]
        acm.describe_certificate.return_value = make_cert_detail()

        records = c.collect()
        assert all(r.customer_id == "TT-0001" for r in records)
