"""Tests for intake extraction and the knowledge graph (no LLM needed)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import graph_store, intake  # noqa: E402
from backend.app.models import Profile  # noqa: E402


# --------------------------------------------------------------------------- #
# intake (the deterministic half)
# --------------------------------------------------------------------------- #
def test_extracts_numbers_and_places_from_english():
    facts = intake.extract("I am 58, a widow in Warangal with 2 acres of land and a white ration card.")
    assert facts["age"] == 58
    assert facts["district"] == "Warangal"
    assert facts["state"] == "Telangana"
    assert facts["land_acres"] == 2.0
    assert facts["is_widow"] is True
    assert facts["income_band"] == "bpl"  # white ration card is the BPL proxy


def test_extracts_from_telugu_and_hindi_scripts():
    telugu = intake.extract(
        "నేను 45 ఏళ్ల రైతు, ఖమ్మం జిల్లా. మాకు 3 ఎకరాల భూమి ఉంది. ఆదాయం సంవత్సరానికి 80000."
    )
    assert telugu["age"] == 45
    assert telugu["district"] == "Khammam"
    assert telugu["annual_income_inr"] == 80000
    assert telugu["occupation"] == "farmer"

    hindi = intake.extract("मैं 30 साल की महिला हूँ, हैदराबाद से। राशन कार्ड है।")
    assert hindi["age"] == 30
    assert hindi["gender"] == "female"
    assert hindi["district"] == "Hyderabad"
    assert hindi["has_ration_card"] is True


def test_post_positioned_negation_is_understood():
    facts = intake.extract("मैं 30 साल की हूँ, सरकारी नौकरी नहीं है।")
    assert facts["is_govt_employee"] is False


def test_short_category_tokens_do_not_match_words_like_student():
    facts = intake.extract("I study in class 10 and I walk to school.")
    assert "social_category" not in facts  # "st" inside "study" must not mean Scheduled Tribe


def test_a_relative_clause_is_not_taken_as_the_applicant():
    facts = intake.extract("I am 58, a widow. My son studies in class 9.")
    assert facts.get("age") == 58
    assert "occupation" not in facts       # the son studies, not the applicant
    assert "class_level" not in facts


def test_lakh_and_thousand_notation():
    assert intake._rupees("income around 1.2 lakh per year") == 120000
    assert intake._rupees("about 60 thousand a year") == 60000


def test_interpret_merges_form_rules_and_never_stores_ids():
    result = intake.interpret(
        "I am 32, a daily wage construction worker in Nizamabad. My aadhaar is 1234 5678 9012.",
        form={"wants_loan": True},
        use_llm=False,
    )
    facts = result["facts"]
    assert facts["occupation"] == "daily_wage"
    assert facts["wants_loan"] is True
    assert "1234 5678 9012" not in result["transcript"]
    assert result["used_llm"] is False
    assert result["field_sources"]["wants_loan"] == "form"
    assert result["field_sources"]["age"] == "rules"


# --------------------------------------------------------------------------- #
# graph
# --------------------------------------------------------------------------- #
def test_graph_links_every_rule_to_a_scheme_and_a_field():
    bundle = graph_store.get_bundle()
    stats = graph_store.graph_stats(bundle)
    assert stats["schemes"] >= 20
    assert stats["edges_by_rel"]["required_by"] == stats["rules"]
    assert stats["edges_by_rel"]["tests"] == stats["rules"]
    assert stats["nodes_by_kind"]["scheme"] == stats["schemes"]


def test_reasoning_paths_cover_every_rule_and_carry_provenance():
    bundle = graph_store.get_bundle()
    profile = Profile(state="Telangana", age=58, is_widow=True, income_band="bpl")
    paths = graph_store.reasoning_paths(bundle, profile)
    total_rules = sum(len(s.rules) for s in bundle.schemes)
    assert len(paths) == total_rules
    assert all(p["path"][-1].startswith("scheme:") for p in paths)
    assert {p["provenance"] for p in paths} <= {"EXTRACTED", "INFERRED", "AMBIGUOUS"}


def test_subgraph_for_profile_marks_missing_facts_as_unknown():
    bundle = graph_store.get_bundle()
    sub = graph_store.subgraph_for_profile(bundle, Profile(), [])
    kinds = {n["kind"] for n in sub["nodes"]}
    assert {"scheme", "rule", "missing"} <= kinds
    assert all(e["status"] == "unknown" for e in sub["edges"] if e["rel"] == "undetermined")


def test_graphify_import_is_optional_and_reported():
    info = graph_store.get_bundle().graphify
    assert "imported" in info and "note" in info
    assert info["imported"] in (True, False)


def test_every_scheme_cites_a_source_and_a_verification_date():
    for scheme in graph_store.get_bundle().schemes:
        assert scheme.source_url.startswith("http"), scheme.id
        assert scheme.verified_on and len(scheme.verified_on) == 10, scheme.id
        assert scheme.provenance in {"EXTRACTED", "INFERRED", "AMBIGUOUS"}, scheme.id
        assert scheme.rules and scheme.documents, scheme.id
