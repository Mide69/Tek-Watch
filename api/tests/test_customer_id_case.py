"""One customer must map to one record, whatever casing arrives.

The Cognito pool is case-insensitive, and such a pool stores and returns the
username lower-cased. Ids are minted and stored uppercase. So a token said
"tt-0001" for a record written as "TT-0001", DynamoDB keys are case-sensitive,
and the customer quietly acquired a second, parallel record: company name,
uploaded logo and issued agent key on one, email, tier and status on the other.
Nothing reported a problem.
"""
import pytest

from auth.dependencies import canonical_customer_id


class TestCanonicalCustomerId:
    def test_folds_the_casing_cognito_returns(self):
        assert canonical_customer_id("tt-0001") == "TT-0001"

    def test_leaves_an_already_canonical_id_alone(self):
        assert canonical_customer_id("TT-9F4KQ7M2") == "TT-9F4KQ7M2"

    def test_folds_mixed_casing(self):
        assert canonical_customer_id("Tt-9f4Kq7M2") == "TT-9F4KQ7M2"

    def test_trims_surrounding_whitespace(self):
        # A stray space in a template parameter would key a third record.
        assert canonical_customer_id("  tt-0001  ") == "TT-0001"

    @pytest.mark.parametrize("empty", ["", None])
    def test_empty_stays_empty_so_the_caller_can_reject_it(self, empty):
        # get_current_customer raises 401 on a falsy id; this must not turn
        # that into the string "NONE" and go looking for a record.
        assert canonical_customer_id(empty) == ""

    def test_every_casing_reaches_the_same_record(self):
        variants = ["tt-0001", "TT-0001", "Tt-0001", "tT-0001", " tt-0001 "]
        assert len({canonical_customer_id(v) for v in variants}) == 1
