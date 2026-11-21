# DEMO.md — the 3-minute run sheet

Open <http://127.0.0.1:8000> (`python run.py`). Keep the browser zoom at ~110%
so the graph labels are readable on a projector.

## 0. The setup line (10s)

> "A family in Warangal is entitled to four or five schemes and knows about one.
> SchemeSetu is not a chatbot that guesses — every verdict on this screen is
> arithmetic over curated rules, and I can show you the rule behind every single
> one."

Point at the status strip: *26 schemes · 123 rules · 315 graph nodes · graphify: 253 extracted nodes (230 bridged) · PII shield ON*.

Point at the topbar mode switch: *"Designed for both the citizen on their phone and the Village Facilitator at the MeeSeva counter with Citizen Mode vs MeeSeva Kiosk Mode."*

Point at the topbar feature buttons:
- **🛡️ Govt Fees**: *"Our Anti-Middleman Shield lists official statutory rates (Income Certificate ₹45, welfare applications FREE) and the ACB helpline 1064, directly stopping broker exploitation."*
- **💼 Who Pays**: *"Answers the business model: MeeSeva VLE franchisees (B2B SaaS), Rural Banks sponsoring BC kiosks for DBT deposit flow, CSR funds, and State Govt ITE&C (B2G)."*
- **🌙 / ☀️ Theme & PWA**: *"Click 🌙 to toggle light/dark theme seamlessly. Show browser address bar: installable PWA with Service Worker offline caching. Press `?` for keyboard shortcuts (`Enter`, `Esc`, `?`)."*
- **👁️ A+**: *"Senior citizen & low-vision accessibility mode with enlarged typography and high contrast."*

## 1. Intake — speak, in your own words (35s)

Click the sample **"Widow, 58, Warangal → pension + health cover"**.

While it loads, say: *"that sentence went through the same pipeline a real
citizen would use — placeholder-free, no forms, no jargon."*

Then show the log line: **"Read 12 facts using rules+llm"** and point out
`Privacy shield: removed Aadhaar number before saving.` — because the sample
deliberately contains an Aadhaar number.

*(Optional, 15s: click **🔊 Telugu: విధవరాలు, 58** — the browser speaks the Telugu prompt aloud via Web Speech API, pulses the sound-wave visualizer, and runs intake live; or press **Speak instead** and say your own sentence.)*

## 2. Results — why, not just what (40s)

Open the top card **Ayushman Bharat PM-JAY**:

- `Likely eligible` badge, confidence, category, provenance tag.
- Walk one line of the list: *"Pass — household falls in the deprived /
  low-income group"*.
- Open **How to apply, step by step** and show that each document says where to
  get it (*"Mahanadi… no — Dharani portal"*).
- Point at the footer: *"verified 2026-11-14 (7 days ago) · National Health
  Authority · source"*.

Point at the headline sentence: *"Three schemes, and the headline separates
`Rs ... in cash support` from `Rs ... of risk cover` — because an insurance policy
that pays out on an event is not money in the hand, and a number that added the two
would be the easiest lie in this product."*

Now open **Aasara Pension (old age)**: verdict `Answer a few questions`, and it
names exactly what is missing — *"not already receiving another government
pension"*.

## 3. The unlock list — the wow moment (25s)

Switch to **Tell us** and look at **"Answer these first"**.

> "This is the answer to 'how do you help someone who doesn't know which details
> matter'. We rank the unanswered facts by how many schemes they decide."

Answer the top question (`Is anyone in the family already getting a government
pension?` → **No**). Press **Answer**. Watch Aasara move to *Likely eligible* and
the headline rupee number change. That re-run is the whole product in one click.

## 4. The reasoning graph — provenance on screen (30s)

Switch to **Why it matched**.

- Green edges from *your facts* into *rules* into *schemes*; dashed yellow edges
  are the facts we still need.
- Click the node **Is a widow** and read the detail panel: status, reason,
  expected value, provenance.
- Click the scheme node **Telangana Aasara Pension - Widow** and show it has two
  edges in — the rules that carry it.

Below, the **Reasoning paths** table lists every one of the 123 rules as
`fact → rule → scheme` with status and provenance. Nothing here is generated
text; it is the graph.

## 4b. The last mile — the artefact, and the eraser (30s, cut first if you are behind)

Switch to **Your schemes** and press **Print / save the checklist** (Ctrl+P shows
the same thing). The print preview replaces the app with one clean page:

> "A verdict on a screen is not an application. This is what the family actually
> carries to the MeeSeva counter — the benefit, the deadline, every paper that is
> compulsory and where to get it, the steps, the portal, and the source with its
> verification date. The rupee total at the top counts transfers and in-kind
> support only; insurance cover is listed separately, because adding the two would
> be lying."

Show the **📲 Send to WhatsApp** and **📱 QR Code for Mobile** buttons:
> "A rural citizen walking away from a MeeSeva counter doesn't carry a printout home — they scan this QR code or receive a pre-formatted WhatsApp message directly on their phone with all their papers and deadlines."

In the **Applications** tracker, press **📱 Preview WhatsApp Reminder**:
> "Here is how our notification engine reaches citizens without requiring an app install: a simulated WhatsApp alert sent 10 days before any scholarship or pension deadline."

For the calendar beat, switch to the **student household** ("SC student, 16,
Hyderabad") and press **Add deadlines to my calendar**: the scholarship windows
are dated, so it queues the nudges and downloads a real `.ics` file. (On the widow
household the matched schemes are rolling, so the app says exactly that instead of
handing you an empty calendar - a good thing to point out if a judge asks.)

Now switch to **Your privacy**:

- read the consent notice out in Telugu from the language selector (notice,
  purpose list, retention window);
- press **Download my data** — one JSON file with every fact, application,
  reminder, consent row and audit entry.

Then press **Delete this household** and confirm:

> "Right to erasure, live. Facts, applications, reminders, consent rows and audit
> rows are gone; one tombstone stays as proof and it contains no personal data.
> The engine still works — it just forgets you."

## 5. Rule Studio — policy as code live (30s)

Switch to **Rule Studio**, pick **Telangana Aasara Pension - Old Age**, change
`aasara.age` from `57` to `60`, press **Simulate**:

- before: *needs_info* (with the amber badge) → after: *Not eligible*.
- Under **Impact on everyone below**, every stored household is re-evaluated live.

> "A policy change is a data edit. The engine that recomputes this is the same
> one that talked to the citizen a minute ago — no model, no black box."

Press **Apply to data file** only if you want to show the `.bak` and the
automatic `provenance: INFERRED` re-tag (do this *after* the main demo if you are
short on time).

## 6. Close — guardrails and the honest bits (20s)

Switch to **Your privacy**:

- patterns active, forbidden fields, redaction count for the session;
- then scroll the raw `/api/health` JSON and point at
  `"fallback_chain": ["groq:…", "openrouter:…"]`.

> "If the network dies or a key is missing, nothing breaks — the deterministic
> engine keeps answering and the UI says which mode it is in. And we never claim
> more than we know: every card says 'likely eligible, not a guarantee'."

## If something goes wrong on stage

| symptom | fix |
|---|---|
| No LLM key / rate-limited | Keep the `use the model` checkbox off; say "running in deterministic mode" — everything else works |
| Voice button says microphone blocked | Skip voice; paste the Telugu sample text instead |
| Graph looks crowded | Use the graph **search** box (e.g. `aasara`) or click a node to focus |
| Numbers look stale | Press `🔄` (reloads `data/schemes.json` and the graph) |
| Need a clean slate | Delete `data/app.db`; it is recreated on the next request |
| Print preview looks empty | You are printing from the wrong tab - the print stylesheet keeps only **Your schemes** |
| Clipboard blocked in the browser | Use **Print / save the checklist** instead; the text is identical |
| A judge asks for the numbers | `python scripts/impact_report.py` prints coverage, rupees, throughput and a determinism check |
| You want proof the rules are sane | `python scripts/lint_data.py` - exits non-zero if any rule is unreachable or unsourced |

## Before you go on stage

```powershell
python -m pytest -q                 # 65 tests
python scripts/lint_data.py         # data + translations + demo households: must PASS
python scripts/impact_report.py     # the numbers you will quote
```
