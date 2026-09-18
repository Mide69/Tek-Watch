"""What a failed compliance control could cost, using published figures only.

Every number here comes from a named public source: the ICO's own statement of
the statutory maximum, ICO penalty notices, or the certification body's
published prices. Nothing is modelled, averaged or predicted, and no number is
presented without the source next to it.

That restraint is the point. A "financial exposure" figure invented by us would
be worth nothing to a business owner and worse than nothing in front of a
regulator. What a small business actually needs to know is narrower and
answerable: what the law allows, what the ICO has actually fined organisations
for this same failing, and what fixing or re-certifying costs. So an estimate
here is three separate things, kept apart:

* the statutory ceiling, which is law, not a prediction
* comparable enforcement, which is what happened to somebody else
* direct cost, which is what the customer will actually spend

Fines depend on turnover, on what the organisation did after the incident, and
on the Commissioner's discretion. None of that is knowable from an AWS
configuration, and the payload says so.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

ICO_MAXIMUM_SOURCE = (
    "https://ico.org.uk/about-the-ico/our-information/policies-and-procedures/"
    "data-protection-fining-guidance/statutory-background/"
    "the-maximum-amount-of-a-fine-under-uk-gdpr-and-dpa-2018/"
)

STATUTORY = "statutory_maximum"
CASE = "enforcement_case"
COST = "direct_cost"


@dataclass(frozen=True)
class Reference:
    id: str
    kind: str
    label: str
    summary: str
    source: str
    published: str
    amount_low: Optional[int] = None    # GBP, None when the figure is a formula
    amount_high: Optional[int] = None
    # FCA and PRA penalties reach regulated firms only. Showing one to a
    # plumber as though it could happen to them would be the same dishonesty
    # as inventing the number.
    applies_to: str = "all"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


REFERENCES: Dict[str, Reference] = {
    ref.id: ref
    for ref in [
        Reference(
            id="ukgdpr_standard_max",
            kind=STATUTORY,
            label="Up to £8.7m or 2% of annual worldwide turnover, whichever is higher",
            summary=(
                "The standard maximum under the UK GDPR and the Data Protection Act 2018. "
                "It is the ceiling that applies to security-of-processing failures under "
                "Article 32. It is a legal maximum, not an expected fine."
            ),
            source=ICO_MAXIMUM_SOURCE,
            published="ICO data protection fining guidance",
            amount_low=None,
            amount_high=8_700_000,
        ),
        Reference(
            id="ukgdpr_higher_max",
            kind=STATUTORY,
            label="Up to £17.5m or 4% of annual worldwide turnover, whichever is higher",
            summary=(
                "The higher maximum, which applies to breaches of the data protection "
                "principles in Article 5, including the integrity and confidentiality "
                "principle in Article 5(1)(f)."
            ),
            source=ICO_MAXIMUM_SOURCE,
            published="ICO data protection fining guidance",
            amount_low=None,
            amount_high=17_500_000,
        ),
        Reference(
            id="ico_advanced_2025",
            kind=CASE,
            label="Advanced Computer Software Group Ltd, £3,070,000",
            summary=(
                "Fined in March 2025 after attackers reached systems through a customer "
                "account that had no multi-factor authentication. Personal data of 79,404 "
                "people was put at risk."
            ),
            source="https://ico.org.uk/action-weve-taken/enforcement/2025/03/advanced-computer-software-group-limited/",
            published="March 2025",
            amount_low=3_070_000,
            amount_high=3_070_000,
        ),
        Reference(
            id="ico_dpp_law_2025",
            kind=CASE,
            label="DPP Law Ltd, £60,000",
            summary=(
                "A law firm fined in April 2025 for infringing Articles 5(1)(f), 32(1), "
                "32(2) and 33(1). Attackers entered through an infrequently used "
                "administrator account with no multi-factor authentication, and the breach "
                "was reported 43 days after it was discovered."
            ),
            source="https://ico.org.uk/action-weve-taken/enforcement/2025/04/dpp-law-ltd/",
            published="April 2025",
            amount_low=60_000,
            amount_high=60_000,
        ),
        Reference(
            id="ico_tuckers_2022",
            kind=CASE,
            label="Tuckers Solicitors LLP, £98,000",
            summary=(
                "Fined in March 2022 after a ransomware attack. The ICO records that "
                "personal data held in backups was not encrypted, and court bundles taken "
                "by the attacker were published on the dark web."
            ),
            source="https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/security/encryption/encryption-scenarios/",
            published="March 2022",
            amount_low=98_000,
            amount_high=98_000,
        ),
        Reference(
            id="fca_tsb_2022",
            kind=CASE,
            label="TSB Bank plc, £48,650,000",
            summary=(
                "Fined in December 2022 by the FCA and the PRA together for operational risk "
                "management and governance failures around an IT migration, including the "
                "management of outsourcing risk. This is the operational resilience regime "
                "PS21/3 sits in."
            ),
            source="https://www.fca.org.uk/news/press-releases/tsb-fined-48m-operational-resilience-failings",
            published="December 2022",
            amount_low=48_650_000,
            amount_high=48_650_000,
            applies_to="fca_regulated",
        ),
        Reference(
            id="fca_equifax_2023",
            kind=CASE,
            label="Equifax Ltd, £11,164,400",
            summary=(
                "Fined in October 2023 for failing to manage and monitor the security of UK "
                "consumer data it had outsourced. The FCA found there were known weaknesses "
                "in the data security systems and that Equifax failed to act on them."
            ),
            source="https://www.fca.org.uk/news/press-releases/equifax-ltd-fine-cyber-security-breach",
            published="October 2023",
            amount_low=11_164_400,
            amount_high=11_164_400,
            applies_to="fca_regulated",
        ),
        Reference(
            id="ce_plus_assessment",
            kind=COST,
            label="Cyber Essentials Plus assessment, about £2,000 to £3,000",
            summary=(
                "IASME, which runs the scheme for the NCSC, puts a Cyber Essentials Plus "
                "assessment at roughly £2,000 to £3,000 depending on the size and "
                "complexity of the network. A failed control means paying this again."
            ),
            source="https://iasme.co.uk/articles/cyber-essentials-and-cyber-essentials-plus-what-is-the-difference/",
            published="IASME published guidance",
            amount_low=2_000,
            amount_high=3_000,
        ),
        Reference(
            id="ce_basic_certification",
            kind=COST,
            label="Cyber Essentials certification, £320 to £600 plus VAT",
            summary=(
                "IASME's published price: £320 plus VAT for a micro organisation of one to "
                "nine people, rising with organisation size."
            ),
            source="https://iasme.co.uk/cyber-essentials/frequently-asked-questions/",
            published="IASME published pricing",
            amount_low=320,
            amount_high=600,
        ),
    ]
}

# Which published references bear on each control, and in one sentence, why.
#
# A control only earns a case reference where the ICO's own account of that case
# names the same failing. The MFA controls cite the two MFA cases because both
# penalty notices turn on an account without MFA; the encryption control cites
# Tuckers because the ICO's encryption guidance uses it as the example of
# unencrypted data at rest. Nothing is attached by loose association.
CONTROL_EXPOSURE: Dict[str, Dict[str, Any]] = {
    "S3-01": {
        "why": (
            "A bucket open to the internet is the clearest form of a confidentiality "
            "failure. If personal data is in it, this is a reportable breach."
        ),
        "references": ["ukgdpr_higher_max", "ukgdpr_standard_max"],
    },
    "S3-02": {
        "why": "Unencrypted storage is the failing the ICO cites in its own encryption guidance.",
        "references": ["ico_tuckers_2022", "ukgdpr_standard_max"],
    },
    "S3-03": {
        "why": (
            "Without versioning there is no way back from deletion or ransomware, which is "
            "the availability limb of Article 32(1)(c)."
        ),
        "references": ["ukgdpr_standard_max"],
    },
    "IAM-01": {
        "why": "An account without MFA is the exact entry route in both ICO cases below.",
        "references": ["ico_advanced_2025", "ico_dpp_law_2025", "ce_plus_assessment"],
    },
    "IAM-02": {
        "why": (
            "The root account can do anything in the account. Both cases below began at an "
            "account with no second factor."
        ),
        "references": ["ico_advanced_2025", "ico_dpp_law_2025", "ce_plus_assessment"],
    },
    "IAM-03": {
        "why": "Old access keys are credentials nobody is watching, and Cyber Essentials tests for this.",
        "references": ["ce_plus_assessment"],
    },
    "ACM-01": {
        "why": "An expired certificate breaks encryption in transit and takes the service down with it.",
        "references": ["ce_plus_assessment"],
    },
    "GD-01": {
        "why": (
            "Without threat detection you cannot show you test and assess your security, "
            "and you are unlikely to notice a breach in time to report it."
        ),
        "references": ["ukgdpr_standard_max"],
    },
    "GD-02": {
        "why": (
            "Open high-severity findings are the state DPP Law was in: something was wrong "
            "and nobody acted, so the 72-hour clock was missed. The FCA fined Equifax for the "
            "same shape of failure: known weaknesses, no action taken."
        ),
        "references": ["ico_dpp_law_2025", "fca_equifax_2023"],
    },
    "RES-01": {
        "why": (
            "A service that cannot survive losing a data centre cannot be shown to stay within "
            "an impact tolerance."
        ),
        "references": ["fca_tsb_2022"],
    },
    "RES-02": {
        "why": "Without backups there is no recovery, which is the heart of operational resilience.",
        "references": ["fca_tsb_2022"],
    },
    "RES-03": {
        "why": "A single-zone entry point takes the whole service down with one zone.",
        "references": ["fca_tsb_2022"],
    },
    "RES-04": {
        "why": (
            "TSB's failures were compounded by not understanding what was happening during the "
            "incident. Alarms are how you find out in time."
        ),
        "references": ["fca_tsb_2022"],
    },
    "CT-01": {
        "why": (
            "Without a trail you cannot show the ICO what happened, which is the "
            "accountability duty in Article 5(2)."
        ),
        "references": ["ukgdpr_higher_max"],
    },
}

BASIS = (
    "Figures are published sources only: the statutory maximum set out by the ICO, ICO and FCA "
    "penalty notices for the same failing, and the certification body's own prices. They are "
    "not a prediction. A fine depends on turnover, on what you do after an incident, and on the "
    "regulator's discretion, none of which can be read from AWS settings. Cases marked as "
    "applying to FCA-regulated firms do not apply to businesses outside that regime."
)


def _money(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    if value >= 1_000_000:
        return f"£{value / 1_000_000:.2f}m".replace(".00m", "m")
    return f"£{value:,}"


def for_control(control_id: str) -> Optional[Dict[str, Any]]:
    """The published exposure attached to one control, or None if none is."""
    mapping = CONTROL_EXPOSURE.get(control_id)
    if not mapping:
        return None
    refs = [REFERENCES[r].as_dict() for r in mapping["references"] if r in REFERENCES]
    if not refs:
        return None
    return {"why": mapping["why"], "references": refs}


def estimate(report: Dict[str, Any]) -> Dict[str, Any]:
    """Exposure for the failing controls in a compliance report.

    Only failing controls count. A control that passed, or that could not be
    read, carries no exposure: saying otherwise would inflate the number with
    things the customer has already done or that we simply cannot see.
    """
    failed = [c for c in report.get("controls", []) if c.get("status") == "fail"]

    items: List[Dict[str, Any]] = []
    cited: Dict[str, Reference] = {}
    for control in failed:
        exposure = for_control(str(control.get("id")))
        if not exposure:
            continue
        items.append({
            "control_id": control.get("id"),
            "control_title": control.get("title"),
            "severity": control.get("severity"),
            "why": exposure["why"],
            "references": exposure["references"],
        })
        for ref in exposure["references"]:
            cited[ref["id"]] = REFERENCES[ref["id"]]

    direct = [r for r in cited.values() if r.kind == COST]
    cases = [r for r in cited.values() if r.kind == CASE]
    statutory = [r for r in cited.values() if r.kind == STATUTORY]

    direct_low = sum(r.amount_low or 0 for r in direct) or None
    direct_high = sum(r.amount_high or 0 for r in direct) or None
    case_low = min((r.amount_low for r in cases if r.amount_low), default=None)
    case_high = max((r.amount_high for r in cases if r.amount_high), default=None)

    return {
        "failing_controls": len(failed),
        "controls_with_published_exposure": len(items),
        "direct_cost": {
            "low": direct_low,
            "high": direct_high,
            "display": (
                f"{_money(direct_low)} to {_money(direct_high)}"
                if direct_low and direct_high and direct_low != direct_high
                else _money(direct_low)
            ),
            "references": [r.as_dict() for r in direct],
        },
        "comparable_enforcement": {
            "low": case_low,
            "high": case_high,
            "display": (
                f"{_money(case_low)} to {_money(case_high)}"
                if case_low and case_high and case_low != case_high
                else _money(case_low)
            ),
            "references": [r.as_dict() for r in cases],
        },
        "statutory_maximum": {
            "references": [r.as_dict() for r in statutory],
            "display": max((r.label for r in statutory), key=len) if statutory else None,
        },
        "items": items,
        "basis": BASIS,
    }
