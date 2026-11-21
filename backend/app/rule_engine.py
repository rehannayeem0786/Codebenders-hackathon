"""Deterministic eligibility engine.

This module is the reason the demo cannot fail: every verdict is produced by
plain comparisons over curated data, never by a language model. The optional
LLM layer may *paraphrase* or *translate* a verdict, but it can never change
one.

Each rule yields pass / fail / unknown:

* ``pass``    - the profile clearly satisfies the rule
* ``fail``    - the profile clearly violates it (hard rules block the scheme)
* ``unknown`` - we do not know that fact yet, so we ask exactly for it
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Optional

from .config import settings
from .models import (
    COVER_CATEGORIES,
    PROFILE_FIELDS,
    FieldQuestion,
    Profile,
    Rule,
    RuleResult,
    Scheme,
    SchemeMatch,
)

_VERDICT_ORDER = {"likely_eligible": 0, "possible": 1, "needs_info": 2, "not_eligible": 3}

# --------------------------------------------------------------------------- #
# coercion helpers - citizens type "Class 9", "9th", "ninth", "B.Tech 2nd year"
# --------------------------------------------------------------------------- #
_WORD_NUMBERS: dict[str, int] = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6,
    "7th": 7, "8th": 8, "9th": 9, "10th": 10, "11th": 11, "12th": 12,
}
_COURSE_NUMBERS: dict[str, int] = {
    "iti": 11, "polytechnic": 11, "diploma": 11, "intermediate": 11, "inter": 11,
    "degree": 13, "graduate": 13, "b.tech": 13, "btech": 13, "b.sc": 13, "bsc": 13,
    "b.com": 13, "bcom": 13, "b.pharm": 13, "pharm": 13,
    "post graduate": 15, "postgraduate": 15, "m.tech": 15, "mtech": 15, "mba": 15,
}


def _num(value: Any) -> Optional[float]:
    """Coerce to float, or ``None`` when the value is not numeric."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(m.group(0)) if m else None


def class_number(value: Any) -> Optional[int]:
    """Best-effort class/year number: ``Class 9``, ``9th``, ``B.Tech 2nd year``."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        n = int(value)
        return n if 1 <= n <= 20 else None
    text = str(value).strip().lower()
    if not text:
        return None
    for key, n in _COURSE_NUMBERS.items():
        if key in text:
            return n
    for key, n in _WORD_NUMBERS.items():
        if re.search(rf"\b{re.escape(key)}\b", text):
            return n
    m = re.search(r"(\d{1,2})", text)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 20 else None
    return None


def _norm(value: Any) -> str:
    return str(value).strip().casefold().replace(" ", "_").replace("-", "_")


def _truthy(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = _norm(value)
    if text in {"yes", "y", "true", "haan", "ha", "avunu", "1", "have", "has"}:
        return True
    if text in {"no", "n", "false", "nahi", "ledu", "0", "none", "dont", "don't"}:
        return False
    return None


def field_label(field: str) -> str:
    meta = PROFILE_FIELDS.get(field)
    return meta["label"] if meta else field.replace("_", " ")


def field_question(field: str) -> str:
    meta = PROFILE_FIELDS.get(field)
    return meta["q"] if meta else f"Please tell us your {field.replace('_', ' ')}."


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "(not answered)"
    return str(value)


def _cmp(op: str, actual: float, expected: float) -> bool:
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    return False


# --------------------------------------------------------------------------- #
# single rule evaluation
# --------------------------------------------------------------------------- #
def evaluate_rule(rule: Rule, profile: Profile, provenance: str = "EXTRACTED") -> RuleResult:
    """Evaluate one rule against one profile. Never raises."""
    known = profile.known()
    has_value = rule.field in known
    actual = known.get(rule.field)
    label = field_label(rule.field)
    result = RuleResult(
        rule_id=rule.id,
        field=rule.field,
        op=rule.op,
        expected=rule.value,
        actual=actual,
        status="unknown",
        hard=rule.hard,
        weight=rule.weight,
        rule_text=rule.text or rule.id,
        evidence=provenance,
        source_note=rule.source_note,
    )

    if not has_value or actual in ("", [], {}):
        result.reason = f"Waiting on your '{label}' to check this rule."
        return result

    op = rule.op
    expected = rule.value

    if op in {"true", "false"}:
        truth = _truthy(actual)
        if truth is None:
            result.reason = f"Could not read '{label}' - please answer yes or no."
            return result
        want = op == "true"
        result.status = "pass" if truth is want else "fail"
        result.reason = (
            f"Your answer for {label} is {format_value(truth)}; "
            f"this rule needs {format_value(want)}."
        )
        return result

    if op == "exists":
        result.status = "pass"
        result.reason = f"You told us your {label}."
        return result

    if op in {"eq", "ne"}:
        same = _norm(actual) == _norm(expected)
        ok = same if op == "eq" else not same
        result.status = "pass" if ok else "fail"
        if op == "eq":
            result.reason = f"{label} is '{format_value(actual)}'; this rule expects '{format_value(expected)}'."
        else:
            result.reason = f"{label} is '{format_value(actual)}'; this rule expects anything other than '{format_value(expected)}'."
        return result

    if op in {"in", "not_in"}:
        options_raw = expected if isinstance(expected, (list, tuple, set)) else [expected]
        options = [_norm(o) for o in options_raw]
        inside = _norm(actual) in options
        ok = inside if op == "in" else not inside
        result.status = "pass" if ok else "fail"
        listed = ", ".join(format_value(o) for o in options_raw)
        if op == "in":
            result.reason = f"{label} is '{format_value(actual)}'; accepted values are: {listed}."
        else:
            result.reason = f"{label} is '{format_value(actual)}'; this scheme excludes: {listed}."
        return result

    if op in {"class_between", "class_gte", "class_lt"}:
        got = class_number(actual)
        if got is None:
            result.reason = f"Could not work out a class number from '{format_value(actual)}'."
            return result
        if op == "class_between":
            bounds = expected if isinstance(expected, (list, tuple)) else [expected, expected]
            lo, hi = int(_num(bounds[0]) or 0), int(_num(bounds[-1]) or 0)
            ok = lo <= got <= hi
            result.reason = f"You are in class/year {got}; this scheme covers {lo}-{hi}."
        elif op == "class_gte":
            want = int(_num(expected) or 0)
            ok = got >= want
            result.reason = f"You are in class/year {got}; this scheme needs class {want} or above."
        else:
            want = int(_num(expected) or 0)
            ok = got < want
            result.reason = f"You are in class/year {got}; this scheme needs below class {want}."
        result.status = "pass" if ok else "fail"
        return result

    # numeric comparisons (gt / gte / lt / lte / between)
    got_n = _num(actual)
    if got_n is None:
        result.reason = f"Cannot compare '{label}' = '{format_value(actual)}' numerically."
        return result
    if op == "between":
        bounds = expected if isinstance(expected, (list, tuple)) else [expected, expected]
        lo, hi = _num(bounds[0]), _num(bounds[-1])
        if lo is None or hi is None:
            result.reason = f"This rule has no usable range ({format_value(expected)})."
            return result
        ok = lo <= got_n <= hi
        result.reason = f"{label} is {got_n:g}; this scheme covers {lo:g} to {hi:g}."
        result.status = "pass" if ok else "fail"
        return result
    want_n = _num(expected)
    if want_n is None:
        result.reason = f"This rule has no usable threshold ({format_value(expected)})."
        return result
    ok = _cmp(op, got_n, want_n)
    word = {"gt": "more than", "gte": "at least", "lt": "less than", "lte": "at most"}.get(op, "comparable to")
    result.reason = f"{label} is {got_n:g}; this scheme needs {word} {want_n:g}."
    result.status = "pass" if ok else "fail"
    return result


# --------------------------------------------------------------------------- #
# whole-scheme verdicts
# --------------------------------------------------------------------------- #
_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_month_day(value: str | None) -> str:
    if not value or "-" not in value:
        return ""
    month, day = value.split("-")[:2]
    try:
        return f"{int(day)} {_MONTHS[int(month)]}"
    except (ValueError, IndexError):
        return value


def describe_deadline(deadline: Any) -> str:
    """A citizen-readable deadline line for a scheme."""
    if deadline is None:
        return "No published deadline"
    kind = getattr(deadline, "type", "rolling")
    note = (getattr(deadline, "note", "") or "").strip()
    if kind == "annual":
        return f"Annual window - usually closes around {_fmt_month_day(getattr(deadline, 'month_day', None))}. {note}".strip()
    if kind == "window":
        return (
            f"Window: {_fmt_month_day(getattr(deadline, 'opens_month_day', None))} to "
            f"{_fmt_month_day(getattr(deadline, 'month_day', None))}. {note}"
        ).strip()
    if kind == "one_time":
        return note or "One-time assistance - apply at the time of the event."
    return note or "Open all year (rolling)."


def evaluate_scheme(
    scheme: Scheme,
    profile: Profile,
    categories: dict[str, str] | None = None,
    today: date | None = None,
) -> SchemeMatch:
    """Evaluate every rule of one scheme and explain the verdict."""
    today = today or date.today()
    categories = categories or {}
    results = [evaluate_rule(r, profile, scheme.provenance) for r in scheme.rules]
    matched = [r for r in results if r.status == "pass"]
    failed = [r for r in results if r.status == "fail"]
    unknown = [r for r in results if r.status == "unknown"]
    hard_failed = [r for r in failed if r.hard]
    soft_failed = [r for r in failed if not r.hard]
    unknown_hard = [r for r in unknown if r.hard]

    if hard_failed:
        verdict = "not_eligible"
    elif unknown_hard:
        verdict = "needs_info"
    elif soft_failed:
        verdict = "possible"
    else:
        verdict = "likely_eligible"

    total_weight = sum(r.weight for r in results) or 1.0
    ratio = sum(r.weight for r in matched) / total_weight
    if verdict == "likely_eligible":
        confidence = 0.72 + 0.25 * ratio
    elif verdict == "possible":
        confidence = 0.40 + 0.30 * ratio
    elif verdict == "needs_info":
        confidence = 0.25 + 0.30 * ratio
    else:
        confidence = 0.10 + 0.20 * (1.0 - ratio)

    days_since = None
    verified = (scheme.verified_on or "").strip()
    if verified:
        try:
            days_since = (today - date.fromisoformat(verified)).days
        except ValueError:
            days_since = None
    stale = days_since is not None and days_since > settings.data_stale_after_days
    if stale:
        confidence *= 0.9
    if scheme.provenance == "AMBIGUOUS":
        confidence *= 0.9
    confidence = round(max(0.02, min(0.97, confidence)), 2)

    why: list[str] = []
    why.append(
        {
            "likely_eligible": "All the rules we could check are satisfied.",
            "possible": "The main rules are satisfied, but some optional conditions are not met.",
            "needs_info": "We need a few more details before we can confirm this.",
            "not_eligible": "A mandatory rule is not met, so this one is not for you right now.",
        }[verdict]
    )
    for r in sorted(matched, key=lambda x: -x.weight)[:6]:
        why.append(f"Pass - {r.rule_text}")
    for r in sorted(soft_failed, key=lambda x: -x.weight)[:3]:
        why.append(f"Met partly / not met - {r.rule_text}")
    for r in sorted(hard_failed, key=lambda x: -x.weight)[:3]:
        why.append(f"Not met - {r.rule_text} ({r.reason})")
    for r in sorted(unknown_hard, key=lambda x: -x.weight)[:4]:
        why.append(f"Need to know - {field_label(r.field)} to check: {r.rule_text}")

    unlock: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    for r in sorted(unknown, key=lambda x: -x.weight):
        if r.field in seen_fields:
            continue
        seen_fields.add(r.field)
        meta = PROFILE_FIELDS.get(r.field, {})
        unlock.append(
            {
                "field": r.field,
                "label": field_label(r.field),
                "question": field_question(r.field),
                "kind": meta.get("kind", "text"),
                "values": list(meta.get("values", [])),
                "for_rule": r.rule_text,
                "weight": r.weight,
            }
        )

    if verified:
        age_note = f"Verified against the official source on {verified}"
        if days_since is not None:
            age_note += f" ({days_since} days ago)"
        why.append(age_note + ".")
    if scheme.provenance == "AMBIGUOUS":
        why.append(
            "Provenance AMBIGUOUS: this rule set changed recently, so treat the figures as "
            "indicative and confirm at the office."
        )

    return SchemeMatch(
        scheme_id=scheme.id,
        name=scheme.name,
        name_local=dict(scheme.name_local),
        level=scheme.level,
        category=scheme.category,
        category_label=categories.get(scheme.category, scheme.category.replace("_", " ").title()),
        summary=scheme.summary,
        benefit=scheme.benefit,
        benefit_value_inr=scheme.benefit_value_inr,
        apply_url=scheme.apply_url,
        source_url=scheme.source_url,
        source_name=scheme.source_name,
        verified_on=scheme.verified_on,
        days_since_verified=days_since,
        deadline=describe_deadline(scheme.deadline),
        verdict=verdict,
        confidence=confidence,
        matched_rules=matched,
        failed_rules=failed,
        unknown_rules=unknown,
        why=why,
        unlock_questions=unlock,
        document_count=len(scheme.documents),
        mandatory_documents=sum(1 for d in scheme.documents if d.mandatory),
        provenance=scheme.provenance,
    )


def rank_matches(matches: list[SchemeMatch]) -> list[SchemeMatch]:
    """Best-first: verdict, then confidence, then value of the benefit."""
    return sorted(
        matches,
        key=lambda m: (
            _VERDICT_ORDER.get(m.verdict, 9),
            -m.confidence,
            -m.benefit_value_inr,
            m.name,
        ),
    )


# --------------------------------------------------------------------------- #
# "which details matter?" - PS5's first question, answered with arithmetic
# --------------------------------------------------------------------------- #
def missing_field_impact(
    schemes: list[Scheme],
    matches: list[SchemeMatch],
    limit: int = 0,
) -> list[FieldQuestion]:
    """Rank unanswered facts by how much answering them would unlock.

    ``unlocks_definite`` counts schemes where this one fact is the *only*
    thing standing between the citizen and a verdict - those are the
    questions worth asking first.
    """
    by_id = {m.scheme_id: m for m in matches}
    buckets: dict[str, dict[str, Any]] = {}
    for scheme in schemes:
        m = by_id.get(scheme.id)
        if m is None or m.verdict in {"not_eligible", "likely_eligible"}:
            continue
        fields: list[str] = []
        for r in m.unknown_rules:
            if r.field in PROFILE_FIELDS and r.field not in fields:
                fields.append(r.field)
        if not fields:
            continue
        share = scheme.benefit_value_inr / len(fields)
        for field in fields:
            bucket = buckets.setdefault(field, {"count": 0, "share": 0.0, "definite": []})
            bucket["count"] += 1
            bucket["share"] += share
            if len(fields) == 1:
                bucket["definite"].append((scheme.name, scheme.benefit_value_inr))

    out: list[FieldQuestion] = []
    for field, bucket in buckets.items():
        meta = PROFILE_FIELDS.get(field, {})
        definite = sorted(bucket["definite"], key=lambda t: -t[1])
        definite_value = round(sum(v for _, v in definite))
        out.append(
            FieldQuestion(
                field=field,
                label=meta.get("label", field),
                question=meta.get("q", f"Please tell us your {field}."),
                kind=meta.get("kind", "text"),
                values=list(meta.get("values", [])),
                unlocks_schemes=[n for n, _ in definite[:5]],
                unlocks_count=bucket["count"],
                unlocks_definite=len(definite),
                potential_value_inr=round(bucket["share"]),
                why=(
                    f"This answer moves about Rs {round(bucket['share']):,} a year across "
                    f"{bucket['count']} scheme(s)"
                    + (
                        f", and decides {len(definite)} of them on its own "
                        f"(worth about Rs {definite_value:,})."
                        if definite
                        else "."
                    )
                ),
            )
        )
    # Rank by the money the answer moves, then by how many schemes it decides
    # outright. This is the "which details matter?" answer in one number.
    out.sort(key=lambda q: (-q.potential_value_inr, -q.unlocks_definite, -q.unlocks_count, q.field))
    return out[:limit] if limit else out


# --------------------------------------------------------------------------- #
# Rule Studio: patch a rule and see the verdict move (deterministic what-if)
# --------------------------------------------------------------------------- #
PATCHABLE = {"op", "value", "weight", "hard", "text", "source_note", "field"}


def apply_rule_overrides(
    scheme: Scheme, overrides: dict[str, dict[str, Any]] | None
) -> tuple[Scheme, dict[str, Any]]:
    """Return ``(patched_scheme, diff)`` for the given rule-id -> patch map."""
    overrides = overrides or {}
    diffs: dict[str, Any] = {}
    patched: list[Rule] = []
    for rule in scheme.rules:
        patch = overrides.get(rule.id) or {}
        clean = {k: v for k, v in patch.items() if k in PATCHABLE and v is not None}
        if clean:
            diffs[rule.id] = {
                "before": rule.model_dump(include=set(clean.keys())),
                "after": clean,
            }
            patched.append(rule.model_copy(update=clean))
        else:
            patched.append(rule)
    return scheme.model_copy(update={"rules": patched}), diffs


def match_summary(matches: list[SchemeMatch]) -> dict[str, Any]:
    """Headline numbers for the results screen."""
    counts = {"likely_eligible": 0, "possible": 0, "needs_info": 0, "not_eligible": 0}
    for m in matches:
        counts[m.verdict] = counts.get(m.verdict, 0) + 1
    def _split(verdict: str) -> tuple[float, float]:
        """Cash first, then risk cover. The two are never added together."""
        cash = sum(
            m.benefit_value_inr
            for m in matches
            if m.verdict == verdict and m.category not in COVER_CATEGORIES
        )
        cover = sum(
            m.benefit_value_inr
            for m in matches
            if m.verdict == verdict and m.category in COVER_CATEGORIES
        )
        return cash, cover

    eligible_cash, eligible_cover = _split("likely_eligible")
    possible_cash, possible_cover = _split("possible")
    eligible_value = eligible_cash + eligible_cover
    possible_value = possible_cash + possible_cover
    return {
        "counts": counts,
        "total": len(matches),
        "likely_eligible_cash_inr": round(eligible_cash),
        "likely_eligible_cover_inr": round(eligible_cover),
        "likely_eligible_value_inr": round(eligible_value),
        "possible_cash_inr": round(possible_cash),
        "possible_cover_inr": round(possible_cover),
        "possible_value_inr": round(possible_value),
        "headline": _headline(counts, eligible_cash, eligible_cover),
    }


def _headline(counts: dict[str, int], cash: float, cover: float) -> str:
    """One honest sentence: cash and risk cover are never merged into a total.

    An insurance policy that pays out when something goes wrong is not money in
    the hand. A headline that added the two would be the easiest lie in the whole
    product - so a cover-only match set says exactly that, and points the citizen
    at the questions that would reveal the cash transfers.
    """
    count = counts["likely_eligible"]
    behind = counts["possible"]
    if cash and cover:
        return (
            f"{count} scheme(s) look likely eligible: about Rs {round(cash):,} a year in cash "
            f"support, plus Rs {round(cover):,} of risk cover that pays out only on an event. "
            f"{behind} more are close behind."
        )
    if cash:
        return (
            f"{count} scheme(s) look likely eligible, worth about Rs {round(cash):,} a year in "
            f"cash support. {behind} more are close behind."
        )
    if cover:
        return (
            f"{count} scheme(s) look likely eligible, and they are all risk cover "
            f"(Rs {round(cover):,}): cover is not cash. Answer the ranked questions below to "
            f"find the cash transfers you may be missing."
        )
    return (
        "No scheme is confirmed yet. Answer the ranked questions below and watch the verdicts move."
    )


VERDICT_LABELS = {
    "likely_eligible": "Likely eligible",
    "possible": "Possible - one condition to check",
    "needs_info": "Answer a few questions",
    "not_eligible": "Not eligible right now",
}

GUARDRAIL_WORDING = (
    "Likely eligible means the rules we know about are satisfied - it is not a guarantee of "
    "approval. The final decision is always the department's."
)
