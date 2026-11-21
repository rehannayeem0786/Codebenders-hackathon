# SchemeSetu — architecture

Written for a judge who has five minutes and wants to know *why* the thing is
built this way, and where a lie could hide. Everything here is checkable in the
repo.

## The one-sentence shape

A deterministic rule engine decides eligibility; a knowledge graph explains the
path that produced each verdict; a language model may read and reword, but never
decide.

```
                    ┌────────────────────── frontend/ (no build step) ───────┐
  citizen ─────────►│ intake · results · reasoning graph (SVG) · tracker ·   │
  typed / spoken /  │ Rule Studio · privacy & data rights · printable list   │
  Telugu Hindi Eng  └────────────▲──────────────────────────────────────────┘
                                 │ JSON over /api (fetch, same origin)
┌────────────────────────────────┴───────────────────────────────────────────┐
│ backend/app/main.py — FastAPI routes, static UI mount, timing/hardening    │
├────────────────────────────────────────────────────────────────────────────┤
│ intake.py       free text/voice ─► facts (keyword rules first, LLM for gaps)│
│ pii.py          redaction shield + forbidden-field policy (on the way in,   │
│                 and again on the way to the database)                      │
│ rule_engine.py  operators, verdicts, confidence, unlock ranking, what-if    │
│ graph_store.py  NetworkX graph, graphify merge, reasoning paths             │
│ store.py        SQLite: profiles, applications, reminders, consent, audit   │
│ llm.py          Groq + OpenRouter chat, Groq Whisper STT, fallbacks         │
│ i18n.py         English / Hindi / Telugu chrome + questions                 │
│ config.py       env-driven settings, provider resolution, guardrail checks  │
└────────────────────────────────────────────────────────────────────────────┘
        ▲                                   ▲
        │ data/schemes.json (26 schemes)    │ graphify-out/graph.json (optional)
        │ corpus/ (source documents)        │ graphifyy merge, provenance-tagged
```

## Request flow for the main path

```
your words ─► pii.redact ─► intake keyword rules ─► (LLM fills gaps only)
                                                          │
                                                          ▼
                                                      Profile
                                                          │
                       ┌──────────────────────────────────┘
                       ▼
        rule_engine.evaluate_scheme × 26 schemes × 123 rules
                       │
        ┌──────────────┼──────────────────────────┐
        ▼              ▼                          ▼
   verdict + why[]  reasoning_paths        missing_field_impact (ranked questions)
        │              │                          │
        └──────────────┴─────────► /api/intake ───┘
                                      │
                    store.save_profile + consent row + reminders
                                      │
                                      ▼
                        frontend: matches, questions, graph
```

## Why the verdict is arithmetic

A rule is data, not code:

```json
{ "id": "aasara.age", "field": "age", "op": "gte", "value": 57,
  "text": "Age 57 years or above (Telangana Aasara threshold)",
  "hard": true, "weight": 2.5, "source_note": "Aasara old-age pension age criterion" }
```

`hard` rules are gates: one failure means "not eligible". Soft rules feed the
confidence score. A rule whose fact is `None` is *unknown*, never guessed, and the
matching missing facts become the ranked question list
(`missing_field_impact`), ordered by the value they would unlock. That ordering is
a pure function of the corpus, so "answer this first" is auditable rather than
rhetorical.

The vocabulary is four verdicts: `likely_eligible`, `possible`, `needs_info`,
`not_eligible`. The UI never says "eligible" — it says "likely eligible, not a
guarantee", and every card names the source and the date it was verified.

## Provenance and freshness

Every scheme carries `source_url`, `source_name`, `verified_on` and a
`provenance` tag:

| Tag | Meaning | Effect on the verdict |
|---|---|---|
| `EXTRACTED` | read off the official page | full confidence |
| `INFERRED` | derived by us (circular, press release) | confidence reduced |
| `AMBIGUOUS` | changed recently / needs a human re-check | confidence reduced and the UI says so |

Aasara pensions and Rythu Bharosa are AMBIGUOUS *on purpose*: their amounts move
every budget, so the app admits it instead of pretending to know. Rules edited
live in Rule Studio are re-tagged `INFERRED` and given `edited_on` and a
`provenance_note`, so a human override can never masquerade as official text.

## Where a lie could hide, and what stops it

| Risk | Control |
|---|---|
| A model inventing an entitlement | The model never returns a verdict — the engine's arithmetic does. The LLM only extracts facts, translates or paraphrases. `LLM_ENABLED=off` is a supported, fully functional mode. |
| Silently unreachable rules (the verdict is always "unknown") | `scripts/lint_data.py` fails on a rule field outside the intake vocabulary, a value outside that field's vocabulary, or an operator/value shape the engine cannot evaluate. It found two such defects in our own corpus. |
| Stale or unsourced rules | Lint requires `source_url`, `source_name` and an ISO `verified_on`; `DATA_STALE_AFTER_DAYS` turns age into a warning and a confidence penalty. |
| Personal data leaking into the database or a prompt | `pii.py` scrubs on intake and again inside `store.save_profile`; forbidden field names are dropped and reported; prompts and replies are scrubbed before and after the call. |
| Data outliving its purpose | Consent rows, export, erasure and the retention sweep are endpoints with tests in `tests/test_privacy_rights.py`. |
| Inflated impact numbers | `scripts/impact_report.py` reports cash and risk cover separately and checks determinism, so the pitch numbers are reproducible rather than rhetorical. |

## Extension points

- **Add a scheme**: append to `data/schemes.json` (with source and provenance),
  drop the source document in `corpus/`, run `python scripts/lint_data.py`, then
  press the reload button in the UI or `POST /api/graph/reload`.
- **Change a rule safely**: Rule Studio → Simulate (impact across every stored
  household) → Apply (writes with a `.bak`, re-tags INFERRED). No redeploy.
- **Add a fact**: add it to `PROFILE_FIELDS` in `models.py`, to the keyword tables
  in `intake.py` if it is spoken, and to `i18n.FIELD_QUESTIONS` in three
  languages — lint enforces the translation coverage.
- **Bring extracted evidence in**: `pip install graphifyy`, then
  `python scripts/graphify_build.ps1`; `GRAPHIFY_AUTO_IMPORT=1` merges
  `graphify-out/graph.json` into the curated graph on startup.

## Verify everything in one go

```powershell
python -m pytest -q                 # 59 tests
python scripts/lint_data.py         # corpus + translations + demo households
python scripts/impact_report.py     # impact and throughput evidence
python scripts/smoke_api.py         # HTTP routes end to end
python scripts/smoke_intake.py      # free text -> facts, three languages
python scripts/smoke_studio.py      # Rule Studio writes, verifies, restores
```

See also `JUDGING.md` (rubric to artefact) and `DEMO.md` (the three-minute run
sheet, including what to do if something fails on stage).
