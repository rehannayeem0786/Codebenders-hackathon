"""Impact and performance evidence for the pitch - numbers, not adjectives.

Run:  python scripts/impact_report.py [--households 500] [--seed 7] [--json out.json]

Builds a deterministic synthetic population that mirrors the target segment in
Telangana (age, gender, rural/urban, income band, occupation, land, widowhood,
disability, ration card, students), then evaluates the *real* deterministic
engine over the whole corpus - no LLM, no network. It reports:

* coverage      - share of households with at least one likely-eligible scheme
* money         - gross yearly value of the schemes those households can claim
* the unknown   - verdicts that still hinge on a fact we were never told
* the fix       - how many ranked questions it takes to close that gap
* throughput    - milliseconds per household across all schemes and rules
* determinism   - the same household evaluated twice must give identical verdicts

Every number printed here is reproducible from the committed seed.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Windows consoles default to cp1252 and crash on Telugu/Hindi output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app import graph_store  # noqa: E402
from backend.app import rule_engine as engine  # noqa: E402
from backend.app.models import COVER_CATEGORIES, Profile  # noqa: E402

DISTRICTS = [
    "Warangal", "Khammam", "Nizamabad", "Karimnagar", "Hyderabad",
    "Rangareddy", "Mahbubnagar", "Adilabad", "Medak", "Nalgonda",
]

# (occupation, relative weight) - rough rural/urban mix for this segment.
OCCUPATION_MIX = [
    ("farmer", 16), ("farm_labour", 12), ("daily_wage", 20), ("gig_worker", 6),
    ("artisan", 8), ("street_vendor", 5), ("student", 10), ("homemaker", 9),
    ("unemployed", 4), ("private_job", 5), ("self_employed", 3), ("retired", 2),
]

INCOME_MIX = [("bpl", 35), ("low", 40), ("middle", 20), ("high", 5)]
CATEGORY_MIX = [("sc", 16), ("st", 9), ("bc", 45), ("obc", 6), ("minority", 12), ("general", 12)]
CLASSES = ["Class 6", "Class 8", "Class 9", "Class 10", "Class 12", "B.Tech 2nd year"]
EDU_FOR_CLASS = {
    "Class 6": "below_8", "Class 8": "class_8", "Class 9": "class_8",
    "Class 10": "class_10", "Class 12": "class_12", "B.Tech 2nd year": "class_12",
}
INCOME_RANGE = {
    "bpl": (30000, 99999), "low": (100000, 299999),
    "middle": (300000, 799999), "high": (800000, 2000000),
}


@dataclass
class HouseholdResult:
    label: str
    definite: int
    possible: int
    needs_info: int
    blocked: int
    value_inr: float
    cash_inr: float
    cover_inr: float
    questions: int
    top_question_flips_something: bool
    unlockable_definite: int


def build_population(count: int, seed: int) -> list[Profile]:
    """Deterministic synthetic households - fictional people, reproducible input."""
    rng = random.Random(seed)
    people: list[Profile] = []
    for index in range(count):
        occupation = rng.choices(
            [name for name, _ in OCCUPATION_MIX], [weight for _, weight in OCCUPATION_MIX]
        )[0]
        income_band = rng.choices(
            [name for name, _ in INCOME_MIX], [weight for _, weight in INCOME_MIX]
        )[0]
        category = rng.choices(
            [name for name, _ in CATEGORY_MIX], [weight for _, weight in CATEGORY_MIX]
        )[0]
        age = rng.choice(
            [rng.randint(18, 25), rng.randint(26, 45), rng.randint(46, 59), rng.randint(60, 82)]
        )
        gender = rng.choices(["female", "male", "other"], [49, 50, 1])[0]
        low, high = INCOME_RANGE[income_band]
        income_inr = rng.randint(low, high)

        facts: dict[str, Any] = {
            "state": "Telangana",
            "district": rng.choice(DISTRICTS),
            "age": age,
            "gender": gender,
            "social_category": category,
            "income_band": income_band,
            "annual_income_inr": income_inr,
            "occupation": occupation,
            "is_rural": rng.random() < 0.62,
            "has_ration_card": rng.random() < 0.85,
            "is_bpl": income_band == "bpl",
            "has_bank_account": rng.random() < 0.82,
            "has_lpg_connection": rng.random() < 0.68,
            "house_type": rng.choices(
                ["pucca", "semi_pucca", "kucha", "rented", "homeless"], [38, 30, 16, 15, 1]
            )[0],
            "family_size": rng.randint(2, 7),
            "marital_status": rng.choices(
                ["married", "single", "widowed", "divorced", "separated"], [58, 30, 7, 3, 2]
            )[0],
            "income_tax_payer": income_band == "high" and rng.random() < 0.6,
            "is_govt_employee": rng.random() < 0.03,
            "has_health_insurance": rng.random() < 0.25,
            "is_unorganised_worker": rng.random() < 0.45,
            "receives_other_pension": age >= 60 and rng.random() < 0.18,
        }

        if occupation in {"farmer", "farm_labour"}:
            facts["land_acres"] = rng.choice([0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0])
            facts["is_rural"] = True
        if occupation == "daily_wage":
            facts["sector"] = rng.choice(["construction", "agriculture", "domestic_work", "driver"])
            facts["is_unorganised_worker"] = True
        if occupation == "gig_worker":
            facts["sector"] = "driver"
            facts["is_unorganised_worker"] = True
        if occupation == "artisan":
            facts["sector"] = rng.choice(["weaving", "pottery", "carpentry", "tailoring"])
        if occupation == "student":
            class_level = rng.choice(CLASSES)
            facts["is_student"] = True
            facts["class_level"] = class_level
            facts["education_level"] = EDU_FOR_CLASS[class_level]
            facts["is_rural"] = False
        if gender == "female" and age >= 55 and facts["marital_status"] == "widowed":
            facts["is_widow"] = True
        if gender == "female" and 18 <= age <= 40 and rng.random() < 0.12:
            facts["is_pregnant_or_lactating"] = True
        if gender == "female" and 20 <= age <= 40 and rng.random() < 0.3:
            facts["children_girl_under10"] = rng.randint(1, 2)
        if rng.random() < 0.09:
            facts["disability_percent"] = rng.choice([40, 50, 60, 75, 90])
        if rng.random() < 0.12:
            facts["wants_loan"] = True
            facts["business_type"] = rng.choice(["small grocery shop", "tailoring unit", "dairy", "auto repair"])

        people.append(Profile(name=f"Household {index + 1:03d}", **facts))
    return people


def _verdicts(profile: Profile, schemes: Any, categories: Any) -> tuple[list[Any], list[Any]]:
    pairs = [(scheme, engine.evaluate_scheme(scheme, profile, categories)) for scheme in schemes]
    return pairs, engine.rank_matches([match for _, match in pairs])


def evaluate(population: list[Profile]) -> dict[str, Any]:
    """Run the real engine over every household and collect the evidence."""
    bundle = graph_store.get_bundle()
    results: list[HouseholdResult] = []
    scheme_value: dict[str, float] = {}
    scheme_cash: dict[str, float] = {}
    scheme_hits: dict[str, int] = {}
    cash_total = 0.0
    cover_total = 0.0
    spread = {"likely_eligible": 0, "possible": 0, "needs_info": 0, "not_eligible": 0}

    started = time.perf_counter()
    for index, profile in enumerate(population):
        _, matches = _verdicts(profile, bundle.schemes, bundle.categories)
        for match in matches:
            spread[match.verdict] = spread.get(match.verdict, 0) + 1
        definite = [match for match in matches if match.verdict == "likely_eligible"]
        cash = sum(m.benefit_value_inr for m in definite if m.category not in COVER_CATEGORIES)
        cover = sum(m.benefit_value_inr for m in definite if m.category in COVER_CATEGORIES)
        cash_total += cash
        cover_total += cover
        for match in definite:
            scheme_hits[match.scheme_id] = scheme_hits.get(match.scheme_id, 0) + 1
            scheme_value[match.scheme_id] = scheme_value.get(match.scheme_id, 0.0) + match.benefit_value_inr
            if match.category not in COVER_CATEGORIES:
                scheme_cash[match.scheme_id] = scheme_cash.get(match.scheme_id, 0.0) + match.benefit_value_inr
        questions = engine.missing_field_impact(bundle.schemes, matches, limit=6)
        results.append(
            HouseholdResult(
                label=profile.name or f"Household {index + 1:03d}",
                definite=len(definite),
                possible=sum(1 for m in matches if m.verdict == "possible"),
                needs_info=sum(1 for m in matches if m.verdict == "needs_info"),
                blocked=sum(1 for m in matches if m.verdict == "not_eligible"),
                value_inr=sum(match.benefit_value_inr for match in definite),
                cash_inr=cash,
                cover_inr=cover,
                questions=len(questions),
                top_question_flips_something=bool(questions and questions[0].unlocks_definite > 0),
                unlockable_definite=questions[0].unlocks_definite if questions else 0,
            )
        )
    elapsed = time.perf_counter() - started

    # Determinism: the same household twice must give the same verdict vector.
    probe = population[0]
    first = [match.verdict for match in _verdicts(probe, bundle.schemes, bundle.categories)[1]]
    second = [match.verdict for match in _verdicts(probe, bundle.schemes, bundle.categories)[1]]

    return {
        "households": len(population),
        "schemes": len(bundle.schemes),
        "rules": sum(len(scheme.rules) for scheme in bundle.schemes),
        "documents": sum(len(scheme.documents) for scheme in bundle.schemes),
        "results": results,
        "spread": spread,
        "scheme_value": scheme_value,
        "scheme_cash": scheme_cash,
        "scheme_hits": scheme_hits,
        "cash_total": cash_total,
        "cover_total": cover_total,
        "elapsed_seconds": elapsed,
        "ms_per_household": (elapsed / max(len(population), 1)) * 1000,
        "deterministic": first == second,
        "engine_seconds_per_scheme_eval": elapsed / max(len(population) * len(bundle.schemes), 1),
    }


def demo_households() -> list[tuple[str, Profile]]:
    """The five committed demo households, through the keyless intake path."""
    from backend.app import intake  # local import: keeps this script importable anywhere

    path = ROOT / "data" / "sample_profiles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[str, Profile]] = []
    for sample in payload.get("samples", []):
        result = intake.interpret(
            sample.get("text", ""),
            form=sample.get("form"),
            use_llm=False,
            language=sample.get("language", "en"),
        )
        out.append((sample.get("title") or sample.get("id", "demo"), result["profile"]))
    return out


def _rupees(value: float) -> str:
    return f"Rs {value:,.0f}"


def render(report: dict[str, Any], seed: int, population: list[Profile]) -> None:
    bundle = graph_store.get_bundle()
    results: list[HouseholdResult] = report["results"]
    households = report["households"]
    definite_households = [row for row in results if row.definite]
    no_answer = [row for row in results if not row.definite and not row.possible]
    cash_values = [row.cash_inr for row in definite_households]
    cash_total = report["cash_total"]
    cover_total = report["cover_total"]
    questions = [row.questions for row in results]
    # Cash and risk cover are reported separately, never summed into one number.

    print("\nSchemeSetu impact report - deterministic engine, no LLM, no network")
    print("=" * 70)
    print(
        f"corpus     : {report['schemes']} schemes / {report['rules']} rules / "
        f"{report['documents']} documents"
    )
    print(
        f"population : {households} synthetic households (seed {seed}) + the 5 committed "
        "demo households"
    )

    print("\nfunnel over the whole population")
    print(
        f"  at least one likely-eligible scheme : {len(definite_households)} "
        f"({len(definite_households) / households:.1%})"
    )
    print(
        f"  nothing they can act on yet         : {len(no_answer)} "
        f"({len(no_answer) / households:.1%})"
    )
    print(f"  over Rs 1 lakh a year in cash       : {sum(1 for v in cash_values if v >= 100000)}")
    print(
        "  verdict spread over all checks      : "
        + ", ".join(f"{key.replace('_', ' ')} {value}" for key, value in report["spread"].items())
    )

    print("\nmoney that reaches the household - transfers and in-kind support")
    print(f"  total unlocked for this population : {_rupees(cash_total)}")
    print(f"  median household                   : {_rupees(statistics.median(cash_values) if cash_values else 0)}")
    print(f"  mean household                     : {_rupees(cash_total / households)}")
    print(f"  scaled to 1 lakh such households   : {_rupees(cash_total / households * 100000)}")
    print(f"  risk cover also unlocked (pays out only if something goes wrong) : {_rupees(cover_total)}")

    print("\nwhere the cash is - top schemes by value delivered")
    ranked = sorted(report["scheme_cash"].items(), key=lambda item: item[1], reverse=True)[:8]
    for index, (scheme_id, value) in enumerate(ranked, 1):
        scheme = bundle.scheme(scheme_id)
        name = (scheme.name if scheme else scheme_id)[:44]
        hits = report["scheme_hits"].get(scheme_id, 0)
        print(f"  {index:>2}. {name:<44} {_rupees(value):>16}  ({hits} households)")

    print("\nthe unknown gap - what one more answer is worth")
    print(
        f"  questions surfaced per household (median / mean) : "
        f"{statistics.median(questions):.0f} / {statistics.mean(questions):.1f}"
    )
    flip = sum(1 for row in results if row.top_question_flips_something)
    print(
        f"  households where the top question decides a scheme : {flip} ({flip / households:.1%})"
    )
    print(
        "  verdicts moved to definite by that one question (mean) : "
        f"{statistics.mean([row.unlockable_definite for row in results]):.1f}"
    )
    unsure = sum(1 for row in results if row.needs_info)
    print(f"  households still carrying a 'we need one fact' verdict : {unsure} ({unsure / households:.1%})")

    print("\nspeed and determinism")
    print(
        f"  {report['ms_per_household']:.1f} ms per household "
        f"({report['schemes']} schemes x {report['rules']} rules)"
    )
    print(f"  ~{1000 / max(report['ms_per_household'], 0.001):.0f} households per second, single process")
    print(f"  identical verdicts on a repeat run : {report['deterministic']}")

    print("\nthe committed demo households (keyless intake path)")
    for title, profile in demo_households():
        _, matches = _verdicts(profile, bundle.schemes, bundle.categories)
        definite = [match for match in matches if match.verdict == "likely_eligible"]
        cash = sum(m.benefit_value_inr for m in definite if m.category not in COVER_CATEGORIES)
        unsure = sum(1 for m in matches if m.verdict == "needs_info")
        print(
            f"  {title[:46]:<46} {len(definite):>2} definite  {_rupees(cash):>13} cash"
            f"   {unsure:>2} awaiting a fact"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SchemeSetu impact and performance evidence")
    parser.add_argument("--households", type=int, default=500, help="synthetic households (default 500)")
    parser.add_argument("--seed", type=int, default=7, help="random seed (default 7)")
    parser.add_argument("--json", type=Path, default=None, help="also write the raw numbers here")
    args = parser.parse_args(argv)

    if args.households < 1:
        print("--households must be at least 1")
        return 1

    population = build_population(args.households, args.seed)
    report = evaluate(population)
    render(report, args.seed, population)

    if args.json:
        payload = {key: value for key, value in report.items() if key != "results"}
        payload["household_results"] = [row.__dict__ for row in report["results"]]
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


