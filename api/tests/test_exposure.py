"""Exposure figures must be published, sourced, and tied to a real failure.

The business plan promised a "regulatory exposure calculator". The danger in
building one is inventing numbers: a made-up fine estimate in front of a
regulator is worse than saying nothing. These tests pin the rules that keep it
honest.
"""
import pytest

from services import exposure


def report(*controls):
    return {"controls": list(controls)}


def control(cid, status="fail", severity="high", title="A control"):
    return {"id": cid, "status": status, "severity": severity, "title": title}


class TestReferences:
    def test_every_reference_names_a_source(self):
        for ref in exposure.REFERENCES.values():
            assert ref.source.startswith("https://"), ref.id
            assert ref.published, ref.id
            assert ref.summary.strip(), ref.id

    def test_every_control_maps_only_to_references_that_exist(self):
        for cid, mapping in exposure.CONTROL_EXPOSURE.items():
            assert mapping["why"].strip(), cid
            for ref_id in mapping["references"]:
                assert ref_id in exposure.REFERENCES, (cid, ref_id)

    def test_case_references_carry_the_amount_actually_fined(self):
        cases = [r for r in exposure.REFERENCES.values() if r.kind == exposure.CASE]
        assert cases
        for ref in cases:
            assert ref.amount_low == ref.amount_high, ref.id  # a fine is one number
            assert ref.amount_low and ref.amount_low > 0, ref.id

    def test_statutory_maximum_is_not_presented_as_an_expected_fine(self):
        for ref in exposure.REFERENCES.values():
            if ref.kind == exposure.STATUTORY:
                assert "maximum" in ref.label.lower() or "up to" in ref.label.lower()

    def test_the_mfa_cases_are_the_ones_attached_to_the_mfa_controls(self):
        # Both ICO notices turn on an account without MFA. That is why they are
        # cited here and nowhere they do not belong.
        for cid in ("IAM-01", "IAM-02"):
            refs = exposure.CONTROL_EXPOSURE[cid]["references"]
            assert "ico_advanced_2025" in refs and "ico_dpp_law_2025" in refs


class TestEstimate:
    def test_a_clean_account_has_no_exposure(self):
        result = exposure.estimate(report(control("S3-01", status="pass"), control("IAM-01", status="pass")))
        assert result["failing_controls"] == 0
        assert result["items"] == []
        assert result["direct_cost"]["low"] is None
        assert result["comparable_enforcement"]["low"] is None

    def test_unknown_controls_do_not_create_exposure(self):
        # We cannot charge a customer for something we could not read.
        result = exposure.estimate(report(control("IAM-01", status="unknown")))
        assert result["items"] == []

    def test_a_failing_control_brings_its_published_references(self):
        result = exposure.estimate(report(control("IAM-02")))
        assert result["failing_controls"] == 1
        item = result["items"][0]
        assert item["control_id"] == "IAM-02"
        labels = [r["label"] for r in item["references"]]
        assert any("Advanced Computer Software" in label for label in labels)
        assert all(r["source"].startswith("https://") for r in item["references"])

    def test_direct_costs_are_counted_once_not_once_per_control(self):
        # Three controls citing the same Cyber Essentials Plus assessment is
        # still one assessment to pay for.
        one = exposure.estimate(report(control("IAM-01")))
        three = exposure.estimate(report(control("IAM-01"), control("IAM-02"), control("IAM-03")))
        assert three["direct_cost"]["high"] == one["direct_cost"]["high"]

    def test_comparable_enforcement_spans_the_cited_cases(self):
        result = exposure.estimate(report(control("IAM-01")))
        assert result["comparable_enforcement"]["low"] == 60_000
        assert result["comparable_enforcement"]["high"] == 3_070_000
        assert result["comparable_enforcement"]["display"] == "£60,000 to £3.07m"

    def test_the_three_kinds_of_number_are_never_added_together(self):
        result = exposure.estimate(report(control("IAM-01"), control("CT-01")))
        assert set(result) >= {"direct_cost", "comparable_enforcement", "statutory_maximum"}
        assert "total" not in result
        assert result["direct_cost"]["high"] != result["comparable_enforcement"]["high"]

    def test_every_payload_states_what_the_numbers_are_not(self):
        result = exposure.estimate(report(control("S3-01")))
        assert "not a prediction" in result["basis"]

    def test_a_control_with_no_published_exposure_is_counted_but_not_invented(self):
        result = exposure.estimate(report(control("XX-99")))
        assert result["failing_controls"] == 1
        assert result["controls_with_published_exposure"] == 0
        assert result["items"] == []


@pytest.mark.parametrize("amount,expected", [
    (60_000, "£60,000"),
    (3_070_000, "£3.07m"),
    (17_500_000, "£17.50m"),
    (None, None),
])
def test_money_formatting(amount, expected):
    assert exposure._money(amount) == expected
