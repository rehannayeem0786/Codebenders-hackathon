"""Honesty tests for the numbers we put on screen.

Cash transfers and risk cover must never be merged into one rupee figure: an
insurance policy that pays out only when something goes wrong is not money in the
hand, and a headline that adds the two is the easiest lie a product like this
could tell. These tests keep that rule enforced in code.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import graph_store  # noqa: E402
from backend.app import rule_engine as engine  # noqa: E402
from backend.app.models import Profile  # noqa: E402

WIDOW = Profile(
    state="Telangana",
    age=58,
    gender="female",
    is_widow=True,
    has_ration_card=True,
    has_bank_account=True,
    land_acres=2,
    income_band="low",
    annual_income_inr=90000,
)

FARMER = Profile(
    state="Telangana",
    age=45,
    gender="male",
    occupation="farmer",
    land_acres=3,
    has_ration_card=True,
    has_bank_account=True,
    is_rural=True,
    income_band="low",
    annual_income_inr=80000,
    income_tax_payer=False,
    is_govt_employee=False,
)


def _summary(profile: Profile) -> dict:
    bundle = graph_store.get_bundle()
    matches = engine.rank_matches(
        [engine.evaluate_scheme(scheme, profile, bundle.categories) for scheme in bundle.schemes]
    )
    return engine.match_summary(matches)


def test_cover_only_household_is_told_that_cover_is_not_cash():
    summary = _summary(WIDOW)
    assert summary["likely_eligible_cover_inr"] > 0, "the widow should match at least one cover scheme"
    assert "risk cover" in summary["headline"]
    assert "cover is not cash" in summary["headline"]
    assert summary["likely_eligible_value_inr"] == (
        summary["likely_eligible_cash_inr"] + summary["likely_eligible_cover_inr"]
    )


def test_headline_quotes_cash_when_cash_exists():
    summary = _summary(FARMER)
    assert summary["likely_eligible_cash_inr"] > 0, "a landholding farmer should match cash support"
    assert "cash support" in summary["headline"]
    assert summary["headline"].startswith(
        f"{summary['counts']['likely_eligible']} scheme(s) look likely eligible"
    )


def test_no_match_at_all_never_invents_a_rupee_figure():
    summary = _summary(Profile(state="Telangana", age=30))
    assert summary["likely_eligible_cash_inr"] >= 0
    if summary["counts"]["likely_eligible"] == 0:
        assert "Rs" not in summary["headline"]
