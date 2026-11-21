"""Tests for the deterministic core: rule engine, PII guardrails, graph, API.

Run:  pytest -q
These tests never call a language model, so they pass with no keys at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import graph_store, pii  # noqa: E402
from backend.app import rule_engine as eng  # noqa: E402
from backend.app.models import Deadline, Profile, Rule, Scheme  # noqa: E402


def _rule(**kwargs) -> Rule:
    base = {"id": "r1", "field": "age", "op": "gte", "value": 18, "text": "adult"}
    base.update(kwargs)
    return Rule(**base)


# --------------------------------------------------------------------------- #
# rule engine operators
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "op,value,profile,expected",
    [
        ("gte", 18, {"age": 20}, "pass"),
        ("gte", 18, {"age": 17}, "fail"),
        ("lt", 60, {"age": 61}, "fail"),
        ("between", [16, 59], {"age": 45}, "pass"),
        ("between", [16, 59], {"age": 60}, "fail"),
    ],
)
def test_numeric_ops(op, value, profile, expected):
    result = eng.evaluate_rule(_rule(op=op, value=value), Profile(**profile))
    assert result.status == expected, result.reason


@pytest.mark.parametrize(
    "field,op,value,profile,expected",
    [
        ("is_widow", "true", None, {"is_widow": True}, "pass"),
        ("is_widow", "false", None, {"is_widow": True}, "fail"),
        ("social_category", "in", ["sc", "st"], {"social_category": "sc"}, "pass"),
        ("social_category", "in", ["sc", "st"], {"social_category": "bc"}, "fail"),
        ("social_category", "not_in", ["general"], {"social_category": "general"}, "fail"),
        ("has_ration_card", "true", None, {"has_ration_card": "yes"}, "pass"),
    ],
)
def test_boolean_and_set_ops(field, op, value, profile, expected):
    result = eng.evaluate_rule(_rule(field=field, op=op, value=value), Profile(**profile))
    assert result.status == expected, result.reason


def test_unknown_when_fact_is_missing():
    result = eng.evaluate_rule(_rule(), Profile())
    assert result.status == "unknown"
    assert "Waiting on" in result.reason


def test_class_level_parsing():
    assert eng.class_number("Class 9") == 9
    assert eng.class_number("9th") == 9
    assert eng.class_number("ninth") == 9
    assert eng.class_number("B.Tech 2nd year") == 13
    assert eng.class_number("ITI") == 11
    assert eng.class_number("") is None


def test_class_between_rule_matches_a_school_student():
    rule = _rule(id="c", field="class_level", op="class_between", value=[9, 10])
    assert eng.evaluate_rule(rule, Profile(class_level="Class 9")).status == "pass"
    assert eng.evaluate_rule(rule, Profile(class_level="Class 11")).status == "fail"


# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #
def _scheme(rules, provenance="EXTRACTED", deadline_type="rolling") -> Scheme:
    return Scheme(
        id="s1",
        name="Test scheme",
        category="health",
        summary="test",
        benefit_value_inr=1000,
        verified_on="2026-11-01",
        provenance=provenance,
        deadline=Deadline(type=deadline_type, month_day="10-31"),
        rules=rules,
    )


def test_all_hard_rules_passing_is_likely_eligible():
    match = eng.evaluate_scheme(_scheme([_rule(field="age", op="gte", value=18)]), Profile(age=30))
    assert match.verdict == "likely_eligible"
    assert match.confidence > 0.7
    assert match.why and match.unlock_questions == []


def test_hard_failure_blocks_the_scheme():
    match = eng.evaluate_scheme(_scheme([_rule(field="age", op="gte", value=60)]), Profile(age=30))
    assert match.verdict == "not_eligible"
    assert any("Not met" in line for line in match.why)


def test_soft_failure_gives_possible_not_blocked():
    scheme = _scheme(
        [_rule(id="a", field="age", op="gte", value=18), _rule(id="b", field="is_rural", op="true", hard=False)]
    )
    assert eng.evaluate_scheme(scheme, Profile(age=30, is_rural=False)).verdict == "possible"


def test_missing_hard_fact_asks_a_question():
    match = eng.evaluate_scheme(_scheme([_rule(field="age", op="gte", value=18)]), Profile())
    assert match.verdict == "needs_info"
    assert match.unlock_questions[0]["field"] == "age"


def test_ambiguous_provenance_lowers_confidence():
    rules = [_rule(field="age", op="gte", value=18)]
    clean = eng.evaluate_scheme(_scheme(rules, provenance="EXTRACTED"), Profile(age=30))
    fuzzy = eng.evaluate_scheme(_scheme(rules, provenance="AMBIGUOUS"), Profile(age=30))
    assert fuzzy.confidence < clean.confidence


def test_missing_field_impact_ranks_the_decisive_fact():
    scheme = _scheme(
        [
            _rule(id="a", field="age", op="gte", value=60),
            _rule(id="b", field="gender", op="in", value=["female"]),
        ]
    )
    profile = Profile(age=65)
    ranked = eng.missing_field_impact([scheme], [eng.evaluate_scheme(scheme, profile)])
    assert ranked[0].field == "gender"
    assert ranked[0].unlocks_definite == 1


def test_rule_overrides_change_the_verdict():
    scheme = _scheme([_rule(id="a", field="age", op="gte", value=57)])
    profile = Profile(age=58)
    assert eng.evaluate_scheme(scheme, profile).verdict == "likely_eligible"
    patched, diff = eng.apply_rule_overrides(scheme, {"a": {"value": 60}})
    assert "a" in diff
    assert eng.evaluate_scheme(patched, profile).verdict == "not_eligible"


def test_deadline_is_described_in_citizen_language():
    assert "31 Oct" in eng.describe_deadline(Deadline(type="annual", month_day="10-31"))


# --------------------------------------------------------------------------- #
# PII guardrails
# --------------------------------------------------------------------------- #
def test_aadhaar_and_phone_are_masked_but_last_four_survive():
    safe, findings = pii.redact("aadhaar 1234 5678 9012, mobile 9876543210")
    assert "1234 5678 9012" not in safe
    assert "9012" in safe
    assert {"aadhaar", "phone"} <= {f.kind for f in findings}
    assert "Privacy shield" in pii.summarise(findings)


def test_forbidden_profile_keys_are_dropped_not_stored():
    clean, report = pii.sanitize_profile(
        {"state": "Telangana", "aadhaar": "1234 5678 9012", "pan": "ABCDE1234F"}
    )
    assert "aadhaar" not in clean and "pan" not in clean
    assert set(report["dropped_keys"]) == {"aadhaar", "pan"}
    assert clean["state"] == "Telangana"


def test_strict_check_refuses_a_raw_id():
    with pytest.raises(pii.SensitiveDataError):
        pii.strict_check("my aadhaar is 1234 5678 9012")


def test_guardrail_report_is_self_describing():
    report = pii.guardrail_report()
    assert report["pii_redaction"] is True
    assert "aadhaar" in report["forbidden_fields"]
    assert any(p["kind"] == "otp" for p in report["patterns_active"])
