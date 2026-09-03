"""Tests for the customer company profile endpoints."""
import pytest
from pydantic import ValidationError

from routers.profile import (
    LOGO_MAX_BYTES,
    LOGO_SIGNATURES,
    PROFILE_FIELDS,
    ProfileUpdate,
    _shape,
)


def _sniff(payload: bytes):
    """Mirror of the endpoint's content sniffing, for signature-level tests."""
    for signature, content_type, extension in LOGO_SIGNATURES:
        if payload.startswith(signature):
            return content_type, extension
    return None, None


class TestDisplayName:
    def test_prefers_company_name(self):
        shaped = _shape({
            "customer_id": "TT-9F4KQ7M2",
            "company_name": "God's Palace",
            "name": "Ada",
        })
        assert shaped["display_name"] == "God's Palace"

    def test_falls_back_to_contact_name(self):
        shaped = _shape({"customer_id": "TT-9F4KQ7M2", "name": "Ada"})
        assert shaped["display_name"] == "Ada"

    def test_falls_back_to_customer_id(self):
        # A brand new account has neither, and the dashboard still needs
        # something to print in the header.
        shaped = _shape({"customer_id": "TT-9F4KQ7M2"})
        assert shaped["display_name"] == "TT-9F4KQ7M2"

    def test_empty_company_name_does_not_win(self):
        shaped = _shape({
            "customer_id": "TT-9F4KQ7M2",
            "company_name": "",
            "name": "Ada",
        })
        assert shaped["display_name"] == "Ada"


class TestShapeDoesNotLeak:
    def test_api_key_hash_is_never_returned(self):
        # The profile row carries the hashed api key alongside the company
        # details. Returning the row directly would have handed it to the
        # browser on every dashboard load.
        shaped = _shape({
            "customer_id": "TT-1",
            "api_key_hash": "a" * 64,
            "company_name": "Acme",
        })
        assert "api_key_hash" not in shaped
        assert "a" * 64 not in str(shaped)


class TestProfileValidation:
    def test_strips_surrounding_whitespace(self):
        assert ProfileUpdate(company_name="  Acme Ltd  ").company_name == "Acme Ltd"

    def test_adds_https_to_a_bare_domain(self):
        assert ProfileUpdate(website="acme.com").website == "https://acme.com"

    def test_keeps_an_explicit_scheme(self):
        assert ProfileUpdate(website="http://acme.com").website == "http://acme.com"

    @pytest.mark.parametrize("hostile", [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
    ])
    def test_rejects_non_http_schemes(self, hostile):
        # The website is rendered as a link on the profile page, so a
        # javascript: url stored here would be stored XSS.
        with pytest.raises(ValidationError):
            ProfileUpdate(website=hostile)

    def test_privileged_fields_are_not_settable(self):
        # subscription_tier, status and aws_account_ids are ours to set.
        # update_customer would accept all three, so the guard has to be here.
        for field in ("subscription_tier", "status", "aws_account_ids"):
            assert field not in PROFILE_FIELDS
            assert field not in ProfileUpdate.model_fields


class TestLogoSniffing:
    def test_accepts_png(self):
        assert _sniff(b"\x89PNG\r\n\x1a\n" + b"rest")[0] == "image/png"

    def test_accepts_jpeg(self):
        assert _sniff(b"\xff\xd8\xff\xe0" + b"rest")[0] == "image/jpeg"

    def test_accepts_gif(self):
        assert _sniff(b"GIF89a" + b"rest")[0] == "image/gif"

    def test_rejects_html_claiming_to_be_an_image(self):
        # The browser's Content-Type is a claim, not evidence. This payload is
        # exactly what a stored-XSS attempt looks like on an upload endpoint.
        assert _sniff(b"<html><script>alert(1)</script></html>") == (None, None)

    def test_rejects_svg(self):
        # SVG is a document format that can carry script. Excluded on purpose,
        # even though it is technically an image.
        assert _sniff(b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>') == (None, None)

    def test_size_cap_is_two_megabytes(self):
        assert LOGO_MAX_BYTES == 2 * 1024 * 1024


class TestAgentQueueArn:
    """The agent's own policy has to name the queue it publishes to.

    Cross-account sending needs both the queue's resource policy and the
    caller's identity policy. The identity policy granted send on the wildcard
    arn:aws:sqs:*:*:tek-watch-ingest-*, and the queue is tek-watch-prod-ingest,
    which does not start with "tek-watch-ingest-". So the first real customer
    agent collected 163 records without an error and was refused at the last
    step with AccessDenied.
    """

    def test_derives_the_arn_from_a_queue_url(self):
        from services.cfn_template import _queue_arn

        assert _queue_arn(
            "https://sqs.eu-west-2.amazonaws.com/409415530028/tek-watch-prod-ingest"
        ) == "arn:aws:sqs:eu-west-2:409415530028:tek-watch-prod-ingest"

    def test_the_old_wildcard_would_not_have_matched(self):
        import fnmatch

        from services.cfn_template import _queue_arn

        arn = _queue_arn(
            "https://sqs.eu-west-2.amazonaws.com/409415530028/tek-watch-prod-ingest"
        )
        assert not fnmatch.fnmatch(arn, "arn:aws:sqs:*:*:tek-watch-ingest-*")

    def test_falls_back_rather_than_failing_to_generate(self):
        from services.cfn_template import _queue_arn

        assert _queue_arn("") == "arn:aws:sqs:*:*:*"
        assert _queue_arn("not-a-url") == "arn:aws:sqs:*:*:*"
