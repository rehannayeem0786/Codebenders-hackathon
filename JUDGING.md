# SchemeSetu — what to look at, and how to check it

One page for a judge: each rubric line, the artefact behind it, and the command or
click that proves it. Nothing here needs an API key.

| Rubric line | Where it lives | How to check it in 30 seconds |
|---|---|---|
| Problem fit (typed *or* spoken, regional language, eligibility, documents, deadlines, guardrails) | intake tab, results cards, "how to apply" details, tracker, privacy tab | Load the *Widow, 58, Warangal* sample, press **Find my schemes**, then read one card top to bottom: verdict, per-rule reasons, documents, steps, deadline, source, guardrail line. |
| Technical depth | `rule_engine.py`, `graph_store.py`, `store.py`, `llm.py`, `scripts/lint_data.py` | `python -m pytest -q` → 65 tests, no model calls. `python scripts/lint_data.py` → corpus/i18n/household integrity gate. |
| Explainability | `why[]` on every match, `/api/graph/paths/{id}`, node inspector | Open **Why it matched** and click any node: it shows the rule's reason, the expected value, your answer and the provenance. |
| Practical impact | ranked questions, tracker, printable checklist, `scripts/impact_report.py` | `python scripts/impact_report.py` then press **Print / save the checklist** on a household. |
| Guardrails & ethics | `pii.py`, consent/export/erase/retention endpoints, AMBIGUOUS provenance | Privacy tab: redaction report + consent notice + **Download my data** + **Delete this household**. |
| Working demo | deterministic core, one-click samples, Rule Studio | `python run.py` with no keys at all, then Rule Studio → **Simulate** → **Apply**. |

## The three moments worth rehearsing

1. **The question that is worth money.** Load a sample, then answer the top-ranked
   question and watch a verdict move. The `why` line states the rupee value that
   answer unlocked.
2. **A rule change, live.** Rule Studio → change a threshold → **Simulate** (same
   engine, every stored household re-scored) → **Apply** (writes to
   `data/schemes.json`, keeps a `.bak`, re-tags the scheme `INFERRED`).
3. **Erase me.** Privacy tab → **Delete this household**: facts, applications,
   reminders and consent rows go, one tombstone stays. The engine keeps working —
   it just forgets you.

## Questions a judge may ask

| Question | Short answer |
|---|---|
| "Is this just an LLM prompt?" | No. Verdicts are arithmetic over `data/schemes.json`. `LLM_ENABLED=off` is a supported mode and the demo runs entirely on it. The model only reads text, translates and paraphrases. |
| "What if the model is down on stage?" | The deterministic path never touches it. `/api/health` shows the active mode; `DEMO.md` has a failure table per component. |
| "How do you know the rules are right?" | Every scheme carries `source_url`, `source_name`, `verified_on` and a provenance tag; `scripts/lint_data.py` fails the build on unreachable rules, missing sources and translation gaps; two AMBIGUOUS schemes exist *because* they are genuinely uncertain. |
| "What about Aadhaar?" | Never requested, and dropped if pasted. The redaction shield runs on intake and again before the database, and the forbidden-field list is shown in the UI. |
| "And my data rights?" | Consent, access, portability, erasure and retention are endpoints with tests (`tests/test_privacy_rights.py`), not slideware. |
| "Does it scale?" | 2.9 ms per household for the entire corpus, single process, no cache: ~340 households/second. The corpus is data, so adding a scheme is a JSON edit plus a lint run. |
| "What is not finished?" | Curated-not-crawled data, one household at a time, and reminder delivery is modelled in-app rather than wired to WhatsApp/SMS. `README.md` lists these under *Limitations, stated plainly*. |

## What we deliberately did not fake

- No invented scheme, benefit amount or eligibility rule: 26 schemes, each with a
  URL and a date.
- No "eligible!" claim anywhere in the UI, and no rupee total that adds insurance
  cover to cash.
- No accuracy number we cannot reproduce: the impact report prints its own
  determinism check and its seed.
