# SchemeSetu — claim what's yours

**An explainable government-scheme eligibility navigator.**
Tell it about your family in your own words — typed or spoken, in Telugu, Hindi or
English — and it finds every scheme you can claim, shows you *why* each one
matched, tells you which single answer would unlock the most, and then walks you
through applying.

> Codebenders ACE Builders Hackathon 2026 · **Problem Statement 5 — "Claim
> What's Yours"** (Citizens & Public Services) · focus region: **Telangana**,
> audience: low-income, daily-wage and unorganised families.

---

## 60-second demo

```powershell
python -m pip install -r requirements.txt
python run.py                 # -> http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000>, click a sample household (for example *"Widow, 58,
Warangal"*), and press **Find my schemes**. Then:

1. **Your schemes** — verdicts with a per-rule explanation under every card.
2. **Answer these first** — the intake tab ranks the unanswered facts by how much
   they unlock, recomputed live each time you answer one.
3. **Why it matched** — the reasoning graph: *your fact → the rule it satisfies →
   the scheme it unlocks*, with green/red/dashed edges and clickable nodes.
4. **Rule Studio** — change a threshold, press **Simulate**, and watch verdicts
   move across every stored household. Press **Apply** to write it into
   `data/schemes.json` (a `.bak` is kept and the scheme is re-tagged `INFERRED`).
5. **Your privacy** — the live guardrail report: what was redacted, what is never
   collected, and how many tokens the shield has removed this session. The same
   tab holds the *data rights*: read the consent notice, download everything we
   hold as JSON, or erase the household outright.
6. **Print / save the checklist** (on **Your schemes**) — the last mile: one
   printable page per household with the benefit, the deadline, the compulsory
   papers and where to get each of them, the steps, the portal URL and the source
   with its verification date. Copy it as text for WhatsApp, or add the deadlines
   to a phone calendar as a `.ics` file.

No API key is required for any of that. With a Groq or OpenRouter key,
free-text intake, voice notes and Telugu/Hindi explanations switch on too.

---

## What makes it different

| | |
|---|---|
| **The verdict is arithmetic, not vibes** | Every match is a chain of comparisons over curated data. The LLM never decides eligibility — it can only *read your words*, *translate* and *paraphrase*. The demo cannot hallucinate a false entitlement on stage. |
| **`pass` / `fail` / `unknown`, never a guess** | A missing fact stays unknown and becomes a question. That is how a citizen who "does not know which details matter" is guided: the ranked question list is generated from the blocker rules themselves. |
| **Every rule carries provenance** | `EXTRACTED` (read off the official page), `INFERRED` (derived by us), `AMBIGUOUS` (changed recently, re-verify). AMBIGUOUS rules visibly lower the confidence score and carry a warning in the UI. |
| **A real knowledge graph** | Schemes, rules, documents, facts, categories and sources are nodes; edges are typed (`tests`, `required_by`, `needs_document`, `verified_from`). Graphify's document extraction merges in with its own `EXTRACTED/INFERRED/AMBIGUOUS` tags. |
| **Speech in, in the citizen's language** | A voice note goes to Groq Whisper server-side, so Telugu/Hindi speakers are not limited by browser speech support or typing ability. Results can be read aloud. |
| **Guardrails you can see** | Aadhaar/PAN/account/OTP are masked before anything is stored or sent to a model (last four digits kept so a citizen can still recognise their own document), forbidden field names are dropped outright, and the verdict wording is always "likely eligible — not a guarantee". |

## Architecture

```
frontend/            single-page UI (no build step): intake wizard, results,
  index.html         reasoning graph (SVG), tracker, Rule Studio, privacy panel
  app.js  styles.css

backend/app/
  config.py          env-driven settings, Groq/OpenRouter resolver, guardrail self-check
  models.py          ~38-fact profile vocabulary + scheme/rule/match models
  rule_engine.py     deterministic evaluator: operators, verdicts, confidence,
                     "which detail matters most", Rule-Studio what-if
  graph_store.py     NetworkX graph, graphify merge, reasoning paths, neighbourhoods
  intake.py          free text/voice -> facts (rules first, LLM only for gaps)
  llm.py             Groq + OpenRouter chat, Groq Whisper speech-to-text, fallbacks
  pii.py             redaction shield + forbidden-field policy (visible in the UI)
  i18n.py            English / Hindi / Telugu strings and questions
  store.py           SQLite: profiles, applications, reminders, audit trail
  main.py            FastAPI routes + serves the UI

data/schemes.json    26 curated schemes, 123 rules, 97 documents, each with
                     source_url + source_name + verified_on + provenance
corpus/              source documents for the graphify extraction pipeline
scripts/             smoke tests, data lint, impact report, graphify_build.ps1
tests/               65 tests, none of which need an API key
```

Request flow for the main path:

```
your words ──► pii.redact ──► intake rules ──► (LLM fills gaps) ──► Profile
                                                                      │
        ┌─────────────────────────────────────────────────────────────┘
        ▼
 rule_engine.evaluate (all 123 rules) ──► verdict + why[] + unlock questions
        │                                            │
        ▼                                            ▼
 graph_store.reasoning_paths                 store.save_profile + reminders
        │
        ▼
 /api/intake  ──►  frontend: matches, questions, graph, tracker
```

## Why this cannot fail on stage

- **Zero-key mode is first-class.** With no keys the app runs fully: intake via
  keyword rules (English/Hindi/Telugu), matching, graph, questions, tracking,
  simulations. `/api/health` says which mode you are in.
- **LLM calls are wrapped, retried and chained.** Groq is tried first, then
  OpenRouter; a 429/5xx/timeout logs, falls back, and the deterministic path
  continues. Prompts *and* replies are PII-scrubbed.
- **Data is local.** SQLite + JSON, no network at runtime except optional model
  calls. `🔄` reloads the data file and the graph from disk.

---

## API (interactive docs at `/docs`)

| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | providers, graph stats, guardrail report, store counts |
| GET | `/api/i18n/{lang}` | UI strings, verdict labels, field questions (`en`/`hi`/`te`) |
| GET | `/api/samples` | ready-made households for a repeatable demo |
| POST | `/api/intake` | `{text, form, language, use_llm, save}` → facts, matches, questions |
| POST | `/api/voice` | audio upload → Groq Whisper → the same intake pipeline |
| POST | `/api/match` | re-run matching for a posted or stored profile |
| GET | `/api/schemes`, `/api/schemes/{id}` | the catalogue, with source and provenance |
| GET | `/api/fields` | the whole fact vocabulary in the chosen language |
| GET | `/api/graph` | whole graph, a scheme's neighbourhood, or a profile's reasoning graph (+ paths) |
| GET | `/api/graph/node/{id}`, `/api/graph/search` | explore one node / search the graph |
| POST | `/api/graph/reload` | re-read `data/schemes.json` and the graphify output |
| GET/POST | `/api/applications`, `/api/applications/{id}/status` | application tracker |
| GET/POST | `/api/reminders`, `/api/reminders/plan`, `/api/reminders/{id}/done` | deadline nudges |
| GET | `/api/narrate/{scheme_id}` | explain a verdict in Telugu/Hindi (LLM, with rule-list fallback) |
| GET | `/api/rule-studio` | every rule, editable |
| POST | `/api/rule-studio/simulate` | patch rules → before/after verdicts + impact on all households |
| POST | `/api/rule-studio/apply` | persist the change to `data/schemes.json` (keeps a `.bak`) |
| GET | `/api/audit` | the append-only trail of what the app did |
| GET | `/api/checklist/{profile_id}` | the printable "carry this to the office" checklist (JSON + plain text) |
| GET | `/api/reminders/calendar.ics` | the queued deadlines as a phone-calendar file |
| GET | `/api/consent/notice` | the plain-language consent notice, in `en`/`hi`/`te` |
| GET/POST | `/api/consent`, `/api/consent/{profile_id}` | consent history / record or withdraw consent |
| GET | `/api/profiles/{profile_id}/export` | data access + portability: everything we hold, as JSON |
| DELETE | `/api/profiles/{profile_id}` | right to erasure: facts, applications, reminders, consents, audit rows |
| POST | `/api/privacy/purge` | run the retention sweep on demand |

Example:

```powershell
curl -s -X POST http://127.0.0.1:8000/api/intake -H "Content-Type: application/json" `
  -d '{\"text\":\"I am 58, a widow in Warangal. White ration card, 2 acres. My aadhaar is 1234 5678 9012.\",\"save\":true}'
```

## Data and provenance policy

`data/schemes.json` holds 26 schemes (Telangana + central), 123 rules and 97
documents. Each scheme stores `source_url`, `source_name`, `verified_on` and a
`provenance` tag; each rule can carry a `source_note` explaining where it came
from. The two AMBIGUOUS schemes (Aasara pensions, Rythu Bharosa) are
*deliberately* marked: their amounts move every budget, so the app says so and
reduces its own confidence instead of pretending to know.

Rules are **data, not code** — which is the whole point of Rule Studio:

```json
{ "id": "aasara.age", "field": "age", "op": "gte", "value": 57,
  "text": "Age 57 years or above (Telangana Aasara threshold)",
  "hard": true, "weight": 2.5, "source_note": "Aasara old-age pension age criterion" }
```

To add a scheme: add a file to `corpus/`, update `data/schemes.json`, set
`verified_on` to today, then press `🔄` in the UI (or `POST /api/graph/reload`).
`tests/test_intake_graph.py::test_every_scheme_cites_a_source_and_a_verification_date`
guards this policy in CI.

### The graphify pipeline

```powershell
pip install graphifyy
python scripts/graphify_build.ps1      # corpus/ -> graphify-out/graph.json
```

The backend imports that file on startup (`GRAPHIFY_AUTO_IMPORT=1`) and merges
its nodes and provenance-tagged edges into the curated graph, bridging extracted
evidence onto schemes and rules. `/api/health` reports the merged counts; the
app works exactly the same without it.

## Impact, measured (not asserted)

`python scripts/impact_report.py --households 300 --seed 7` builds a deterministic
synthetic population that mirrors the target segment and runs the *real* engine
over the whole corpus — no LLM, no network. Every number is reproducible from the
committed seed:

| Metric (300 households · 26 schemes · 123 rules) | Value |
|---|---|
| Households with at least one likely-eligible scheme | 268 (89.3%) |
| Households with nothing actionable yet | 5 (1.7%) |
| Median cash unlocked per household | ₹77,600 a year |
| Mean cash unlocked per household | ₹105,787 a year |
| Risk cover detected (health / accident / crop) | ₹26.97 crore — reported separately, never added to cash |
| Households carrying at least one "we need one more fact" verdict | 298 (99.3%) |
| Engine throughput | 2.9 ms per household (26 schemes × 123 rules) |
| Determinism | identical verdicts on a repeat run of the same household |

Two honest readings. Insurance cover dwarfs cash, so the two are reported
separately — summing them would inflate the pitch. And 99.3% of households carry
at least one unanswered question, which is exactly why the core interaction is the
*ranked question* rather than a longer list of schemes.

## Your data, your rights (DPDP Act 2023)

Redaction answers "what do you collect?". This answers "what can I do about it?" —
implemented, not promised:

| Right | How it works |
|---|---|
| Notice | `GET /api/consent/notice` returns a plain-language notice in the citizen's language, with the purpose list and a notice version. |
| Consent | Every saved intake writes a consent row: purposes, language, timestamp, notice version. It can be withdrawn (`POST /api/consent` with `granted=false`). With `CONSENT_REQUIRED=1`, an intake without consent is refused with 403. |
| Access & portability | `GET /api/profiles/{id}/export` returns every fact, application, reminder, consent row and audit entry as one JSON file — one click in the privacy tab. |
| Erasure | `DELETE /api/profiles/{id}` ("Delete this household") removes the facts, applications, reminders, consent rows and audit rows, then writes a single tombstone that proves the erasure and holds no personal data. |
| Retention | Households older than `DATA_RETENTION_DAYS` (default 90) are erased by a sweep at boot and on demand via `POST /api/privacy/purge`. |
| Minimisation | The forbidden-field policy drops Aadhaar/PAN/OTP/account fields before anything is stored — which is also why they can never turn up in an export. |

## Languages

Everything the citizen reads exists in **English, Hindi and Telugu**: UI chrome,
verdict labels, category names and the 35 fact questions. Free-text extraction
understands keyword tables in all three scripts (occupation, category, place
names, negation, numeracy in lakh/thousand), and the optional LLM layer adds
paraphrasing and `narrate` explanations in the same languages. Speech-to-text is
Groq Whisper, so voice input is not limited to browsers that support Indian
languages in Web Speech.

## Configuration

Copy `.env.example` to `.env`. Only two providers are wired in — both are
OpenAI-compatible, so they share one code path:

| variable | default | notes |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` (Groq first, then OpenRouter) / `groq` / `openrouter` |
| `GROQ_API_KEY` | – | <https://console.groq.com/keys> |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | model ids differ per account: check `GET /openai/v1/models` |
| `GROQ_REASONING_EFFORT` | `low` | stops reasoning models from spending the answer budget on thinking |
| `GROQ_STT_ENABLED`, `GROQ_STT_MODEL` | `1`, `whisper-large-v3` | server-side speech-to-text |
| `OPENROUTER_API_KEY` | – | <https://openrouter.ai/keys>, works as the fallback |
| `OPENROUTER_MODEL` | `meta-llama/llama-3.3-70b-instruct` | any OpenRouter id, including `:free` variants |
| `LLM_ENABLED` | `auto` | set `off` to hard-disable all model calls |
| `PII_REDACTION` | `1` | masks Aadhaar/PAN/mobile/account/OTP/email/IFSC |
| `BLOCK_SENSITIVE_IDS` | `1` | drops forbidden field names; conflicts with `PII_REDACTION=0` raise at startup |
| `DATA_STALE_AFTER_DAYS` | `180` | older `verified_on` dates lower the confidence score |
| `GRAPHIFY_AUTO_IMPORT` | `1` | merge `graphify-out/graph.json` when present |
| `STATE_FOCUS` | `Telangana` | demo focus region |
| `DATA_RETENTION_DAYS` | `90` | households older than this are erased by the retention sweep |
| `CONSENT_REQUIRED` | `0` | set `1` and an intake without `consent=true` is refused (403) |

## Tests

```powershell
python -m pytest -q                      # 65 tests, no API key needed
python -m pytest -q                      # 65 tests, no API key needed
python scripts/lint_data.py              # corpus + i18n + demo-household integrity gate
python scripts/impact_report.py          # synthetic-population impact and speed evidence
python scripts/smoke_api.py              # end-to-end HTTP checks across the routes
python scripts/smoke_intake.py           # free text -> facts, in three languages
python scripts/smoke_llm.py              # provider chain, JSON mode, latency
python scripts/smoke_studio.py           # Rule Studio apply/restore (writes, verifies, restores)
```

`lint_data.py` is the reason the evidence base stays trustworthy: it fails the
build on a rule whose field the intake layer could never fill, an operator/value
shape the engine cannot evaluate, a missing source or verification date, a
duplicate id, or an i18n string missing from one of the three languages. It
caught two real defects in our own corpus (a category value that did not exist in
the vocabulary, and a PMSBY rule that read `occupation` where the data was a
`trade`), which is exactly the class of bug that silently turns verdicts into
"unknown".

---

## How this maps to the judging criteria

| Criterion | Where to look |
|---|---|
| **Problem fit** | PS5 asks for typed-or-spoken multi-language intake, scheme discovery with the rule shown, document guidance, deadline alerts and guardrails — each is a screen: intake, results with `why[]`, "how to apply" steps with document sources, the tracker + reminders, and the privacy panel. |
| **Technical depth** | Deterministic rule engine with weights, class-level parsing, unknown-as-unknown verdicts; NetworkX knowledge graph with typed edges and path finding; graphify provenance merge; SQLite persistence with an audit trail; graceful multi-provider LLM layer; 65 tests plus a data-lint gate that fails the build on unreachable rules. |
| **Technical depth** | Deterministic rule engine with weights, class-level parsing, unknown-as-unknown verdicts; NetworkX knowledge graph with typed edges and path finding; graphify provenance merge; SQLite persistence with an audit trail; graceful multi-provider LLM layer; 65 tests plus a data-lint gate that fails the build on unreachable rules. |
| **Explainability** | Every card lists the rules it passed, failed and still needs, names the source and the verification date, and the graph view lets you click any node to see the rule's reason, expected value and provenance. |
| **Practical impact** | The ranked "answer this and you unlock ₹X" list turns an overwhelming search into two or three questions; the tracker converts a match into a filed application with a deadline nudge; the printable checklist is the artefact the household actually carries to the MeeSeva counter. |
| **Guardrails & ethics** | Redaction is on by default and *visible*; forbidden fields are dropped and reported; AMBIGUOUS data lowers confidence and says so; wording is always "likely eligible — not a guarantee"; the app never asks for a full ID; and the DPDP Act 2023 rights (consent, access, portability, erasure, retention) are implemented endpoints, not slide promises. |
| **Working demo** | Deterministic core means zero-key, offline-safe demos; one click loads a sample household; Rule Studio proves the whole thing is data-driven, live. |

## Limitations, stated plainly

- **Curated, not yet auto-updated.** 26 schemes with dated sources are curated by
  hand; the graphify pipeline is the beginning of automating extraction, not the
  end of it. Rules that move every budget are tagged AMBIGUOUS on purpose.
- **Single-profile model.** One household at a time (the person applying). A
  family-member matrix (who is eligible for what) is the natural next step.
- **Eligibility ≠ application accepted.** The verdict is a rules check; the
  department decides. The UI says this on every card.
- **Distribution is out of scope for the demo.** Reminders are modelled in-app;
  wiring them to WhatsApp/SMS needs a provider account and consent flow.
- **Not a legal or financial authority.** Amounts and ceilings are indicative and
  must be confirmed at the office or on the official portal.

## Next, if we keep building

1. Turn `corpus/` into a scheduled extraction job that proposes rule diffs, with
   a human approving each change into `data/schemes.json` (provenance stays honest).
2. Field-worker mode: a panchayat/MeeSeva operator can run intake for many
   households, with an offline-first queue.
3. Fit-scoring across the whole family, plus "you were rejected for X because of
   Y — here is Z instead".
4. A Telugu voice-first flow where Whisper transcribes *and* the app answers by
   voice, tested with real users at a MeeSeva centre.

## Repo conventions

- Python 3.11, FastAPI + Pydantic v2, stdlib SQLite, NetworkX, httpx. No build
  step for the front end: `frontend/` is served by FastAPI at `/`.
- Every module has a docstring explaining *why* it exists, not just what it does.
- Tests never call a model; the deterministic path is the contract.
- Commit `data/`, not `data/app.db`. `.env` is git-ignored; `.env.example` is the
  contract.

## Deployment and security

### Windows quick-start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py                            # then open http://localhost:8000
```

### Tests and data check

```powershell
python -m pytest -q                      # 65 tests
python -m pytest -q                      # 65 tests
python scripts\lint_data.py              # data check
```

### Admin token

The Rule Studio apply and retention purge endpoints require the header
`X-Admin-Token`. Set it with the env var `ADMIN_TOKEN`:

```powershell
$env:ADMIN_TOKEN="your-secret"
```

If `ADMIN_TOKEN` is unset, the app uses an insecure dev default and logs a warning.
Set it for any real deployment. The browser UI asks for the token on the first
Rule Studio apply and keeps it in session storage.

### CORS

Allowed origins come from the env var `CORS_ORIGINS` (comma-separated). The default
is `localhost:8000` and `localhost:5173`.

### Docker

```powershell
docker build -t schemesetu .
docker run --rm -p 8000:8000 --env-file .env schemesetu
```

The `.env` file is excluded from the image, so pass it at run time.

