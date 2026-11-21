"""Data-quality gate for the curated corpus, the translations and the demo households.

Run:  python scripts/lint_data.py
Exit code 0 = the evidence base is self-consistent; 1 = it is not.

This is the check that keeps a hand-curated rule base honest. It refuses to let
through:

* a rule on a field the intake layer can never fill - the verdict could never move
* a rule whose operator/value shape cannot be evaluated by the engine
* a scheme with no source_url / source_name / verified_on
* a duplicate scheme id, rule id or document id
* a scheme citing a category that meta.categories does not define
* a UI string missing from one of the three languages
* a demo household using a field outside the vocabulary

Warnings (verified_on ageing past DATA_STALE_AFTER_DAYS, a scheme with no local
name) do not fail the build, but they are printed so nothing rots silently.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, get_args

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Windows consoles default to cp1252 and crash on Telugu/Hindi output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app import i18n  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.models import PROFILE_FIELDS, Rule, SchemeBook  # noqa: E402

ALLOWED_OPS: set[str] = set(get_args(Rule.model_fields["op"].annotation))
NEEDS_LIST = {"in", "not_in"}
NEEDS_PAIR = {"between", "class_between"}
NEEDS_NOTHING = {"true", "false", "exists"}
NEEDS_NUMBER = {"gt", "gte", "lt", "lte", "class_gte", "class_lt"}
PROVENANCE = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        print(f"[info] {message}")


def _days_since(value: str) -> int | None:
    try:
        return (date.today() - date.fromisoformat(value)).days
    except (TypeError, ValueError):
        return None


def _lint_rule(report: Report, scheme_id: str, rule: Any, seen: set[str]) -> None:
    tag = f"{scheme_id}/{rule.id}"
    if rule.id in seen:
        report.error(f"{tag}: duplicate rule id")
    seen.add(rule.id)
    if rule.op not in ALLOWED_OPS:
        report.error(f"{tag}: unknown operator '{rule.op}'")
        return
    if rule.field not in PROFILE_FIELDS:
        report.error(f"{tag}: field '{rule.field}' is not in the intake vocabulary")
    if rule.op in NEEDS_LIST and not isinstance(rule.value, list):
        report.error(f"{tag}: '{rule.op}' needs a list value, got {type(rule.value).__name__}")
    if rule.op in NEEDS_LIST and isinstance(rule.value, list) and not rule.value:
        report.error(f"{tag}: '{rule.op}' has an empty value list")
    if rule.op in NEEDS_PAIR and not (isinstance(rule.value, list) and len(rule.value) == 2):
        report.error(f"{tag}: '{rule.op}' needs a [low, high] value")
    if rule.op in NEEDS_NOTHING and rule.value not in (None, True, False):
        report.warn(f"{tag}: '{rule.op}' ignores its value ({rule.value!r})")
    if rule.op in NEEDS_NUMBER and not isinstance(rule.value, (int, float)):
        report.error(f"{tag}: '{rule.op}' needs a number, got {rule.value!r}")
    if rule.field in {"class_level", "education_level"} and rule.op in {"eq", "ne"}:
        report.warn(f"{tag}: use class_* operators for '{rule.field}' - string compare is brittle")
    # A rule written against a value the vocabulary does not contain can never
    # match, which silently turns every verdict into "unknown".
    vocabulary = PROFILE_FIELDS.get(rule.field, {}).get("values") or []
    if vocabulary and rule.op in NEEDS_LIST and isinstance(rule.value, list):
        unknown = [value for value in rule.value if value not in vocabulary]
        if unknown:
            report.error(f"{tag}: {unknown} not in the '{rule.field}' vocabulary {vocabulary}")
    if vocabulary and rule.op in {"eq", "ne"} and rule.value not in vocabulary:
        report.error(f"{tag}: '{rule.value}' is not a valid '{rule.field}' value {vocabulary}")
    if not rule.text:
        report.warn(f"{tag}: no human-readable text for the citizen")
    if rule.weight <= 0:
        report.error(f"{tag}: weight must be positive (got {rule.weight})")


def lint() -> Report:
    report = Report()
    book = SchemeBook(**json.loads(settings.schemes_path.read_text(encoding="utf-8")))
    categories = set((book.meta.get("categories") or {}).keys())
    rules = sum(len(scheme.rules) for scheme in book.schemes)
    docs = sum(len(scheme.documents) for scheme in book.schemes)
    report.note(f"corpus: {len(book.schemes)} schemes, {rules} rules, {docs} documents")

    seen_schemes: set[str] = set()
    for scheme in book.schemes:
        tag = f"scheme {scheme.id}"
        if scheme.id in seen_schemes:
            report.error(f"{tag}: duplicate scheme id")
        seen_schemes.add(scheme.id)

        for field in ("name", "summary", "category", "source_url", "source_name", "verified_on"):
            if not getattr(scheme, field):
                report.error(f"{tag}: missing '{field}'")
        if scheme.source_url and not scheme.source_url.startswith("http"):
            report.error(f"{tag}: source_url is not a URL ({scheme.source_url})")
        if scheme.category and scheme.category not in categories:
            report.error(f"{tag}: category '{scheme.category}' is not declared in meta.categories")
        if scheme.provenance not in PROVENANCE:
            report.error(f"{tag}: provenance '{scheme.provenance}' is not one of {sorted(PROVENANCE)}")
        if scheme.benefit_value_inr < 0:
            report.error(f"{tag}: negative benefit value")
        if not scheme.apply_url and not scheme.apply_steps:
            report.error(f"{tag}: neither apply_url nor apply_steps - the citizen cannot act on it")
        if not scheme.rules:
            report.error(f"{tag}: no rules, so a verdict can never be computed")

        age = _days_since(scheme.verified_on)
        if age is None:
            report.error(f"{tag}: verified_on is not an ISO date ({scheme.verified_on!r})")
        elif age > settings.data_stale_after_days:
            report.warn(f"{tag}: verified {age} days ago (policy {settings.data_stale_after_days})")
        if not scheme.name_local.get("te") or not scheme.name_local.get("hi"):
            report.warn(f"{tag}: name_local is missing Hindi and/or Telugu")

        seen_rules: set[str] = set()
        for rule in scheme.rules:
            _lint_rule(report, scheme.id, rule, seen_rules)

        seen_docs: set[str] = set()
        for doc in scheme.documents:
            if not doc.label:
                report.error(f"{tag}/{doc.id}: document without a label")
            if doc.id in seen_docs:
                report.error(f"{tag}/{doc.id}: duplicate document id")
            seen_docs.add(doc.id)
        if scheme.documents and not any(doc.mandatory for doc in scheme.documents):
            report.warn(f"{tag}: no document is marked compulsory")
        if not scheme.documents:
            report.warn(f"{tag}: no documents listed")

    # translations
    for key, translations in i18n.UI.items():
        for code in i18n.LANGUAGES:
            if not translations.get(code):
                report.error(f"i18n '{key}': missing '{code}'")

    # demo households
    try:
        payload = json.loads(settings.samples_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.error(f"sample profiles unreadable: {exc}")
        payload = {}
    samples = payload.get("samples", [])
    report.note(f"samples: {len(samples)} demo households")
    for sample in samples:
        sid = sample.get("id", "?")
        if not sample.get("title") or not sample.get("text"):
            report.error(f"sample {sid}: needs both a title and a text")
        if sample.get("language", "en") not in i18n.LANGUAGES:
            report.error(f"sample {sid}: language '{sample.get('language')}' is not supported")
        for field in (sample.get("form") or {}):
            if field not in PROFILE_FIELDS:
                report.error(f"sample {sid}: form field '{field}' is not in the vocabulary")
    if not samples:
        report.warn("no demo households at all - the demo has nothing to click")

    counts = {tag: sum(1 for s in book.schemes if s.provenance == tag) for tag in sorted(PROVENANCE)}
    report.note("provenance: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    stale = [s.id for s in book.schemes if (_days_since(s.verified_on) or 0) > settings.data_stale_after_days]
    if stale:
        report.warn(f"{len(stale)} scheme(s) past the freshness window: {', '.join(stale)}")
    return report


def main() -> int:
    report = lint()
    for message in report.warnings:
        print(f"[warn] {message}")
    for message in report.errors:
        print(f"[FAIL] {message}")
    print(
        f"\n{'PASS' if not report.errors else 'FAIL'}: "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
