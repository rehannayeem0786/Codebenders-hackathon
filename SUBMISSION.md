# SchemeSetu — submission sheet

Ready-to-paste text for the Codebenders ACE Builders Hackathon 2026 form.

> **Fill these three things before you paste anything:** the exact team name from
> your registration (see *Team* below), the member names/roles and college/city,
> and the public GitHub repository URL. Everything else is final and matches the
> code as committed.

## Project name

**SchemeSetu** — *"the bridge to what's already yours"*

## One-line description (for the form)

> An explainable government-scheme eligibility navigator: a family describes its
> situation in Telugu, Hindi or English — typed or spoken — and SchemeSetu
> returns every scheme they can claim, the exact rule behind each verdict, the
> one answer that would unlock the most, and the documents to carry to the office.

## Short description (≈100 words)

Every year thousands of crores of welfare money goes unclaimed because families
do not know what they qualify for, and the rules are buried in portals written in
English. SchemeSetu turns that into a conversation. The citizen speaks; a
deterministic rule engine over 26 curated Telangana + central schemes returns a
`likely eligible / possible / needs-info / not eligible` verdict for each one,
with the rule-by-rule reason, the source and the date it was verified. A
knowledge graph shows *fact → rule → scheme*. A ranked question list tells them
which single detail unlocks the most money. A tracker files the application and
nudges on deadlines. Aadhaar/PAN/account numbers are stripped before anything is
stored or sent to a model.

## Problem statement

**Problem Statement 5 — "Claim What's Yours"** (Citizens & Public Services).
Focus region for this build: **Telangana**; audience: low-income, daily-wage and
unorganised families.

## What we built (highlights)

- **Deterministic eligibility engine (123 rules, 26 schemes)** — the LLM never decides; zero false entitlements.
- **Ranked "which details matter" question loop** with a rupee value per answer, so an overwhelming search becomes two or three questions.
- **Knowledge graph** of schemes/rules/documents/facts/sources with provenance tags (`EXTRACTED` / `INFERRED` / `AMBIGUOUS`), with Graphify document extraction merged (253 extracted nodes, 230 evidence links bridging to curated rules).
- **Dual-Mode deployment**: **Citizen Mode** (simple, regional voice-first, warm intuitive feel) vs **MeeSeva / CSC Kiosk Operator Mode** (high-density triage, token generation, citizen slip).
- **Progressive Web App (PWA) & Offline-First**: Service worker with cache-first static assets, PWA manifest, custom SVG favicon, and zero-network operational capability.
- **Light/Dark Cyber Theme Toggle**: Instant 🌙/☀️ toggle with persistent localStorage preference and high-contrast styling.
- **Senior Citizen Accessibility (👁️ A+)**: One-click enlargement of typography and touch targets for elderly citizens.
- **Anti-Middleman Shield & Statutory Fees Modal**: Clear guidance on free vs paid services (Income cert ₹45, application FREE) and Telangana Anti-Corruption Bureau (ACB) helpline 1064.
- **Sustainable Business Model & Deployment Strategy**: 4-pillar monetization map answering *"Who Pays"* (MeeSeva VLE franchisees, BC Rural Banks, CSR grants, and State Government B2G).
- **Financial Impact Hero Dashboard** with strict honesty: separates direct cash DBT from risk/health cover.
- **Interactive Document Readiness Checklist**: Checkboxes with live percentage tracking, fee & office guidance.
- **1-Click WhatsApp Dispatcher (`wa.me`) & offline pure vector SVG QR Code Generator** for instant phone handover.
- **Simulated WhatsApp Reminder Notification dialog** for low-literacy citizens.
- **Speech-to-text via Groq Whisper and live browser Web Speech API** for Telugu, Hindi & English with sound-wave visualizer.
- **Visual scanning features**: Category emoji icons (🌾, 🏥, 🎓, etc.), verdict color stripes on cards, loading animations, toast notifications, and celebration confetti.
- **PII guardrails** as a visible feature, with a live redaction report.
- **DPDP Act 2023 data rights** implemented end to end: consent notice and withdrawal, one-click data export, one-click erasure, and a 90-day retention sweep.
- **The last mile**: A printable citizen voucher with QR code, WhatsApp text, and a `.ics` calendar file for deadlines.
- **Rule Studio**: Edit a rule, see verdicts move across every stored household, then write it back to the data file (with backup and honest provenance re-tagging).
- **Application tracker + deterministic deadline reminders + audit trail (SQLite)**.
- **65 tests, a data-lint gate** that fails the build on unreachable or unsourced rules, an impact report over a synthetic population, and end-to-end smoke scripts — all runnable with **no API key**.

## Team

- Team name: **Codebenders** *(fill in the exact team name from the registration)*
- Members: *(name — role)*
  - *Member 1 — full-stack / rule engine*
  - *Member 2 — data curation / Telugu-Hindi content*
  - *Member 3 — frontend / demo*
- College / city: *(fill in)*

## Links

- GitHub repository: https://github.com/rehannayeem0786/Codebenders-hackathon.git
- Demo video: *(optional, 2–3 minutes, follow `DEMO.md`)*
- Live link: not hosted for the demo — runs locally with two commands (below).
- Data sources: every scheme in `data/schemes.json` carries its official
  `source_url` and `verified_on` date.

## How to run (for the judges)

```powershell
python -m pip install -r requirements.txt
python run.py            # then open http://127.0.0.1:8000
```

Optional (upgrades free-text/voice intake and Telugu-Hindi explanations): copy
`.env.example` to `.env` and add `GROQ_API_KEY` and/or `OPENROUTER_API_KEY`.
Without them the app runs in deterministic mode, and the status bar says so.

## What to look at first

1. `DEMO.md` — the 3-minute run sheet, including the last-mile and erasure moments.
2. `JUDGING.md` — each rubric line mapped to the artefact and the command that proves it.
3. `ARCHITECTURE.md` — why the core is deterministic, and where a lie could hide.
4. `backend/app/rule_engine.py` — why a verdict cannot be hallucinated.
5. `backend/app/graph_store.py` — how "show me the rule behind this" works.
6. `backend/app/pii.py` — the guardrails, and why they are visible.
7. `data/schemes.json` — the curated rules, sources and provenance tags.
