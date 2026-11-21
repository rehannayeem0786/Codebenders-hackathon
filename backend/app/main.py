"""FastAPI application: the citizen API plus the demo UI.

Route map (all JSON unless noted):

* ``/api/health``                 - what is live: providers, graph, guardrails
* ``/api/i18n/{lang}``            - UI strings in English / Hindi / Telugu
* ``/api/intake``                 - free text or voice transcript -> facts -> matches
* ``/api/voice``                  - audio upload -> Groq Whisper -> the same pipeline
* ``/api/match``                  - re-run matching for a stored or posted profile
* ``/api/schemes``, ``/api/schemes/{id}`` - the curated catalogue
* ``/api/graph`` ...              - the reasoning graph, search and neighbourhoods
* ``/api/applications``, ``/api/reminders`` - tracking
* ``/api/checklist/{id}``         - the printable "carry this to the office" list
* ``/api/reminders/calendar.ics`` - the same deadlines as a phone-calendar file
* ``/api/profiles/{id}/export``   - data access / portability (DPDP Act 2023)
* ``/api/profiles/{id}`` DELETE, ``/api/privacy/purge`` - right to erasure + retention
* ``/api/consent``                - what the citizen agreed to, and when
* ``/api/rule-studio``            - edit a rule, see the verdict move, export the file
* ``/api/narrate/{scheme_id}``    - LLM explanation in Telugu/Hindi (optional)
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import time
import urllib.parse
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Optional

from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import graph_store, i18n, intake, llm, pii, store
from . import rule_engine as engine
from .config import settings
from .models import APPLICATION_STATUSES, Application, COVER_CATEGORIES, Profile

log = logging.getLogger("schemesetu.api")
FRONTEND_DIR = settings.root / "frontend"

_DEFAULT_CORS_ORIGINS = (
    "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()
if not ADMIN_TOKEN:
    ADMIN_TOKEN = "dev-admin-token"
    log.warning(
        "ADMIN_TOKEN is not set: using the insecure default admin token. "
        "Set the ADMIN_TOKEN environment variable for any real deployment."
    )


def _require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Gate privileged routes behind the ``X-Admin-Token`` header (constant-time compare)."""
    if not x_admin_token or not hmac.compare_digest(
        x_admin_token.encode("utf-8"), ADMIN_TOKEN.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="admin token required")



@asynccontextmanager
async def lifespan(_: FastAPI):
    """Housekeeping at boot: enforce the retention window (DPDP Act 2023)."""
    try:
        swept = store.purge_expired()
        if swept["count"]:
            log.info("retention sweep erased %s household(s)", swept["count"])
    except Exception:  # never let cleanup block the demo
        log.warning("retention sweep skipped", exc_info=True)
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    description=(
        "Explainable government-scheme eligibility navigator. "
        "Deterministic rule engine + knowledge graph + optional Groq/OpenRouter layer."
    ),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def _observe(request: Request, call_next: Any) -> Response:
    """Timing + hardening headers. The engine's speed is a feature: prove it."""
    started = time.perf_counter()
    response: Response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-SchemeSetu-Engine"] = "deterministic"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Always answer with JSON. The LLM layer can fail; the product still works."""
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "path": request.url.path,
            "detail": str(exc)[:300],
            "hint": (
                "Eligibility never depends on a model. Retry, or run keyless "
                "(LLM_ENABLED=off) - the deterministic engine answers regardless."
            ),
        },
    )



# --------------------------------------------------------------------------- #
# request bodies
# --------------------------------------------------------------------------- #
class IntakeBody(BaseModel):
    text: str = ""
    language: str = "en"
    form: Optional[dict[str, Any]] = None
    use_llm: bool = True
    save: bool = True
    plan_reminders: bool = False
    # DPDP Act 2023: record what the citizen agreed to, in the language they saw.
    consent: bool = True
    consent_purposes: list[str] = []


class MatchBody(BaseModel):
    profile: Optional[Profile] = None
    profile_id: Optional[str] = None
    language: str = "en"
    save: bool = False
    plan_reminders: bool = False
    include_not_eligible: bool = True


class ApplicationBody(BaseModel):
    profile_id: str
    scheme_id: str
    scheme_name: str = ""
    status: str = "not_started"
    notes: str = ""
    deadline: Optional[str] = None
    documents_ready: list[str] = []
    reference_no: str = ""


class RuleOverride(BaseModel):
    op: Optional[str] = None
    value: Any = None
    weight: Optional[float] = None
    hard: Optional[bool] = None
    text: Optional[str] = None
    source_note: Optional[str] = None
    field: Optional[str] = None


class StudioBody(BaseModel):
    scheme_id: str
    overrides: dict[str, RuleOverride] = {}
    profile_id: Optional[str] = None
    language: str = "en"
    persist: bool = False


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _load_profile(profile: Optional[Profile], profile_id: Optional[str]) -> Profile:
    if profile is not None:
        return profile
    if profile_id:
        stored = store.profile_object(profile_id)
        if stored is None:
            raise HTTPException(status_code=404, detail=f"Unknown profile '{profile_id}'.")
        return stored
    raise HTTPException(status_code=400, detail="Provide either a profile or a profile_id.")


def _localise_match(match: engine.SchemeMatch, lang: str) -> dict[str, Any]:
    data = match.model_dump()
    data["verdict_label"] = i18n.verdict_label(match.verdict, lang)
    data["category_label"] = i18n.category_label(match.category, lang, match.category_label)
    data["unlock_questions"] = [
        {**q, "question": i18n.field_question(q.get("field", ""), lang, str(q.get("question", "")))}
        for q in match.unlock_questions
    ]
    data["guardrail"] = engine.GUARDRAIL_WORDING
    return data


def match_bundle(
    profile: Profile,
    *,
    lang: str = "en",
    save: bool = False,
    profile_id: Optional[str] = None,
    plan_reminders: bool = False,
    include_not_eligible: bool = True,
) -> dict[str, Any]:
    """Evaluate every scheme, rank the results, then explain what is still unknown."""
    bundle = graph_store.get_bundle()
    pairs = [(s, engine.evaluate_scheme(s, profile, bundle.categories)) for s in bundle.schemes]
    matches = engine.rank_matches([m for _, m in pairs])
    questions = engine.missing_field_impact(bundle.schemes, matches, limit=6)

    pid = profile_id
    reminders: list[dict[str, Any]] = []
    if save or plan_reminders:
        pid = store.save_profile(profile, profile_id=profile_id, meta={"language": lang})
        if plan_reminders:
            reminders = store.plan_reminders(pid, pairs)

    return {
        "profile_id": pid,
        "profile": profile.model_dump(exclude_none=True),
        "summary": engine.match_summary(matches),
        "matches": [
            _localise_match(m, lang)
            for m in matches
            if include_not_eligible or m.verdict != "not_eligible"
        ],
        "next_questions": [
            {**q.model_dump(), "question": i18n.field_question(q.field, lang, q.question)}
            for q in questions
        ],
        "reminders_created": reminders,
        "graph_stats": graph_store.graph_stats(bundle),
        "guardrails": {"wording": engine.GUARDRAIL_WORDING, "session": pii.stats()},
        "language": i18n.normalise(lang),
    }


def _scheme_payload(scheme: Any, lang: str = "en") -> dict[str, Any]:
    categories = graph_store.get_bundle().categories
    data = scheme.model_dump()
    data["category_label"] = i18n.category_label(scheme.category, lang, categories.get(scheme.category, ""))
    data["deadline_text"] = engine.describe_deadline(scheme.deadline)
    data["rule_count"] = len(scheme.rules)
    data["local_name"] = scheme.name_local.get(i18n.normalise(lang), "")
    return data


# --------------------------------------------------------------------------- #
# meta endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict[str, Any]:
    """One call that proves what is live - shown on the demo's status bar."""
    bundle = graph_store.get_bundle()
    stats = graph_store.graph_stats(bundle)
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "state_focus": settings.state_focus,
        "default_language": settings.default_language,
        "llm": llm.health(),
        "graph": {
            key: stats[key]
            for key in (
                "nodes",
                "edges",
                "schemes",
                "rules",
                "documents",
                "nodes_by_kind",
                "edges_by_provenance",
                "graphify",
                "loaded_at",
            )
        },
        "guardrails": pii.guardrail_report(),
        "data_rights": {
            "consent_required": settings.consent_required,
            "retention_days": settings.data_retention_days,
            "notice_version": store.NOTICE_VERSION,
            "purposes": store.CONSENT_PURPOSES,
            "route_map": {
                "notice": "/api/consent/notice",
                "record_or_withdraw": "POST /api/consent",
                "export": "/api/profiles/{id}/export",
                "erase": "DELETE /api/profiles/{id}",
                "retention_sweep": "POST /api/privacy/purge",
                "printable_checklist": "/api/checklist/{id}",
                "calendar": "/api/reminders/calendar.ics",
            },
        },
        "store": store.stats(),
        "languages": i18n.LANGUAGES,
        "engine": {"verdicts": engine.VERDICT_LABELS, "wording": engine.GUARDRAIL_WORDING},
    }


@app.get("/api/i18n/{lang}")
def translations(lang: str = "en") -> dict[str, Any]:
    return i18n.payload(lang)


@app.get("/api/samples")
def samples() -> dict[str, Any]:
    """Ready-made households for a fast, repeatable demo."""
    path = settings.samples_path
    if not path.exists():
        return {"samples": [], "note": "data/sample_profiles.json not found"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"samples": [], "note": f"could not read samples: {exc}"}
    return payload if isinstance(payload, dict) else {"samples": payload}


# --------------------------------------------------------------------------- #
# catalogue
# --------------------------------------------------------------------------- #
@app.get("/api/schemes")
def list_schemes(
    q: str = "",
    category: str = "",
    level: str = "",
    lang: str = "en",
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    needle = q.strip().lower()
    rows = []
    for scheme in bundle.schemes:
        if category and scheme.category != category:
            continue
        if level and scheme.level != level:
            continue
        if needle and needle not in f"{scheme.name} {scheme.summary} {' '.join(scheme.tags)}".lower():
            continue
        rows.append(_scheme_payload(scheme, lang))
    return {
        "count": len(rows),
        "schemes": rows[:limit],
        "categories": bundle.categories,
        "meta": {k: v for k, v in bundle.book.meta.items() if k != "categories"},
    }


@app.get("/api/schemes/{scheme_id}")
def scheme_detail(scheme_id: str, lang: str = "en") -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    scheme = bundle.scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Unknown scheme '{scheme_id}'.")
    payload = _scheme_payload(scheme, lang)
    payload["graph"] = graph_store.neighbourhood(bundle, f"scheme:{scheme_id}", depth=1)
    return payload


@app.get("/api/fields")
def field_vocabulary(lang: str = "en") -> dict[str, Any]:
    """The full fact vocabulary, in the citizen's language - powers the wizard."""
    from .models import PROFILE_FIELDS

    rows = []
    for key, meta in PROFILE_FIELDS.items():
        rows.append(
            {
                "field": key,
                "label": meta.get("label", key),
                "kind": meta.get("kind", "text"),
                "values": meta.get("values", []),
                "question": i18n.field_question(key, lang, str(meta.get("q", ""))),
            }
        )
    return {"count": len(rows), "fields": rows, "language": i18n.normalise(lang)}


# --------------------------------------------------------------------------- #
# the main citizen path: own words in, matches out
# --------------------------------------------------------------------------- #
@app.post("/api/intake")
def do_intake(body: IntakeBody = Body(...)) -> dict[str, Any]:
    if settings.consent_required and not body.consent:
        raise HTTPException(
            status_code=403,
            detail=(
                "Consent is required. Read the notice at /api/consent/notice and retry with "
                "consent=true."
            ),
        )
    result = intake.interpret(
        body.text, form=body.form, use_llm=body.use_llm, language=body.language
    )
    profile: Profile = result.pop("profile")
    bundle = match_bundle(profile, lang=body.language, save=body.save, plan_reminders=body.plan_reminders)
    if body.save and bundle.get("profile_id"):
        bundle["consent"] = store.record_consent(
            bundle["profile_id"],
            body.consent_purposes,
            granted=body.consent,
            language=body.language,
        )
    result["profile"] = profile.model_dump(exclude_none=True)
    return {"intake": result, **bundle}


@app.post("/api/voice")
async def do_voice(
    file: UploadFile = File(...),
    language: str = Query("te"),
    use_llm: bool = Query(True),
    save: bool = Query(True),
) -> dict[str, Any]:
    """Voice note -> Groq Whisper -> the normal intake and matching pipeline."""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty audio upload.")
    if len(audio) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Voice note too large (12 MB max).")
    stt = llm.transcribe(
        audio,
        filename=file.filename or "voice.webm",
        content_type=file.content_type or "audio/webm",
        language=language,
    )
    if stt is None:
        raise HTTPException(
            status_code=503,
            detail="Speech-to-text is off. Set GROQ_API_KEY and GROQ_STT_ENABLED=1 - typing still works.",
        )
    if not stt.ok or not stt.text:
        raise HTTPException(
            status_code=502,
            detail=f"Could not transcribe that recording: {stt.error or 'empty transcript'}",
        )
    result = intake.interpret(stt.text, use_llm=use_llm, language=language)
    profile: Profile = result.pop("profile")
    bundle = match_bundle(profile, lang=language, save=save)
    result["profile"] = profile.model_dump(exclude_none=True)
    return {"stt": stt.as_dict(), "intake": result, **bundle}


@app.post("/api/match")
def do_match(body: MatchBody) -> dict[str, Any]:
    profile = _load_profile(body.profile, body.profile_id)
    return match_bundle(
        profile,
        lang=body.language,
        save=body.save,
        profile_id=body.profile_id,
        plan_reminders=body.plan_reminders,
        include_not_eligible=body.include_not_eligible,
    )


@app.get("/api/profiles")
def list_profiles(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    return {"profiles": store.list_profiles(limit)}


@app.get("/api/profiles/{profile_id}")
def profile_detail(profile_id: str, lang: str = "en") -> dict[str, Any]:
    stored = store.get_profile(profile_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Unknown profile '{profile_id}'.")
    profile = Profile(**stored["facts"])
    data = match_bundle(profile, lang=lang, profile_id=profile_id)
    data["stored"] = stored
    data["audit"] = store.list_audit(profile_id, limit=20)
    return data


@app.get("/api/audit")
def audit(profile_id: Optional[str] = None, limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
    return {"entries": store.list_audit(profile_id, limit)}


# --------------------------------------------------------------------------- #
# the reasoning graph
# --------------------------------------------------------------------------- #
@app.get("/api/graph")
def graph(
    profile_id: Optional[str] = None,
    scheme_id: Optional[str] = None,
    depth: int = Query(1, ge=1, le=3),
    include_not_eligible: bool = True,
) -> dict[str, Any]:
    """Whole-graph overview, one scheme's neighbourhood, or a profile's reasoning graph."""
    bundle = graph_store.get_bundle()
    if scheme_id:
        return graph_store.neighbourhood(bundle, f"scheme:{scheme_id}", depth=depth)
    if profile_id:
        profile = _load_profile(None, profile_id)
        pairs = [(s, engine.evaluate_scheme(s, profile, bundle.categories)) for s in bundle.schemes]
        matches = engine.rank_matches([m for _, m in pairs])
        sub = graph_store.subgraph_for_profile(
            bundle, profile, matches, include_not_eligible=include_not_eligible
        )
        sub["paths"] = graph_store.reasoning_paths(bundle, profile, limit=400)
        sub["stats"] = graph_store.graph_stats(bundle)
        return sub
    sub = graph_store.subgraph_for_profile(bundle, Profile(), [], include_not_eligible=True)
    sub["stats"] = graph_store.graph_stats(bundle)
    return sub


@app.get("/api/graph/search")
def graph_search(q: str = "", limit: int = Query(25, ge=1, le=100)) -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    return {"query": q, "results": graph_store.search(bundle, q, limit)}


@app.get("/api/graph/node/{node_id:path}")
def graph_node(node_id: str, depth: int = Query(1, ge=1, le=3)) -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    return graph_store.neighbourhood(bundle, node_id, depth)


@app.get("/api/graph/paths/{profile_id}")
def graph_paths(profile_id: str, limit: int = Query(600, ge=1, le=2000)) -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    profile = _load_profile(None, profile_id)
    return {"profile_id": profile_id, "paths": graph_store.reasoning_paths(bundle, profile, limit)}


@app.post("/api/graph/reload")
def graph_reload() -> dict[str, Any]:
    """Re-read ``data/schemes.json`` and the graphify output (used after edits)."""
    graph_store.invalidate()
    return graph_store.graph_stats(graph_store.get_bundle())


# --------------------------------------------------------------------------- #
# tracking: applications and reminders
# --------------------------------------------------------------------------- #
class StatusBody(BaseModel):
    status: str
    notes: str = ""
    reference_no: str = ""


class PlanBody(BaseModel):
    profile_id: str
    days_before: int = 10


@app.get("/api/applications")
def list_applications(profile_id: Optional[str] = None) -> dict[str, Any]:
    return {"applications": store.list_applications(profile_id), "statuses": APPLICATION_STATUSES}


@app.post("/api/applications")
def upsert_application(body: ApplicationBody) -> dict[str, Any]:
    if body.status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {APPLICATION_STATUSES}")
    app_id = store.upsert_application(Application(**body.model_dump()))
    return {"id": app_id, "applications": store.list_applications(body.profile_id)}


@app.post("/api/applications/{app_id}/status")
def set_application_status(app_id: int, body: StatusBody) -> dict[str, Any]:
    if body.status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {APPLICATION_STATUSES}")
    current = next((a for a in store.list_applications() if a["id"] == app_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Unknown application {app_id}.")
    payload = {
        **current,
        "status": body.status,
        "notes": body.notes or current.get("notes", ""),
        "reference_no": body.reference_no or current.get("reference_no", ""),
    }
    store.upsert_application(Application(**payload))
    return {"applications": store.list_applications(current["profile_id"])}


@app.get("/api/reminders")
def list_reminders(profile_id: Optional[str] = None, status: Optional[str] = None) -> dict[str, Any]:
    return {"reminders": store.list_reminders(profile_id, status)}


@app.get("/api/reminders/due")
def due_reminders(window_days: int = Query(7, ge=1, le=90)) -> dict[str, Any]:
    return {"due": store.due_reminders(window_days=window_days)}


@app.post("/api/reminders/plan")
def plan_reminders(body: PlanBody) -> dict[str, Any]:
    """Queue deadline nudges for one household - deterministic, no cron needed."""
    bundle = graph_store.get_bundle()
    profile = _load_profile(None, body.profile_id)
    pairs = [(s, engine.evaluate_scheme(s, profile, bundle.categories)) for s in bundle.schemes]
    created = store.plan_reminders(body.profile_id, pairs, days_before=body.days_before)
    return {"created": created, "reminders": store.list_reminders(body.profile_id)}


@app.post("/api/reminders/{reminder_id}/done")
def complete_reminder(reminder_id: int) -> dict[str, Any]:
    return {"ok": store.complete_reminder(reminder_id)}


@app.get("/api/narrate/{scheme_id}")
def narrate(scheme_id: str, profile_id: Optional[str] = None, lang: str = "te") -> dict[str, Any]:
    """Explain one scheme in Telugu/Hindi (LLM), falling back to the rule list."""
    bundle = graph_store.get_bundle()
    scheme = bundle.scheme(scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Unknown scheme '{scheme_id}'.")
    profile = _load_profile(None, profile_id) if profile_id else Profile()
    match = engine.evaluate_scheme(scheme, profile, bundle.categories)
    spoken = intake.narrate(match, lang)
    return {
        "scheme_id": scheme_id,
        "scheme_name": scheme.name,
        "verdict": match.verdict,
        "verdict_label": i18n.verdict_label(match.verdict, lang),
        "confidence": match.confidence,
        "why": match.why,
        "guardrail": engine.GUARDRAIL_WORDING,
        **spoken,
    }


# --------------------------------------------------------------------------- #
# data rights: consent, access, erasure, retention (DPDP Act 2023)
# --------------------------------------------------------------------------- #
CONSENT_NOTICE = {
    "en": (
        "SchemeSetu uses the details you give only to check which schemes you may be eligible "
        "for, to explain each verdict in your language, to build your document checklist, and to "
        "send deadline reminders. We never ask for or store your Aadhaar, PAN, OTP or bank "
        "account number. You can download everything we hold, or have it erased, at any time."
    ),
    "hi": (
        "SchemeSetu आपके विवरण का उपयोग केवल यह जाँचने के लिए करता है कि आप किन योजनाओं के पात्र हो "
        "सकते हैं, हर निर्णय का कारण आपकी भाषा में बताने, दस्तावेज़ सूची बनाने और समय-सीमा की याद "
        "दिलाने के लिए। हम कभी आधार, पैन, ओटीपी या बैंक खाता संख्या नहीं माँगते। आप कभी भी अपना "
        "पूरा डेटा डाउनलोड या मिटवा सकते हैं।"
    ),
    "te": (
        "SchemeSetu మీరు ఇచ్చిన వివరాలను మీకు ఏ పథకాలు వర్తిస్తాయో తనిఖీ చేయడానికి, ప్రతి నిర్ణయానికి "
        "కారణం మీ భాషలో వివరించడానికి, పత్రాల జాబితా తయారు చేయడానికి, గడువు రిమైండర్లు పంపడానికి "
        "మాత్రమే ఉపయోగిస్తుంది. ఆధార్, పాన్, ఓటీపీ లేదా బ్యాంకు ఖాతా నంబర్ మేము ఎప్పుడూ అడగము. "
        "మేము ఉంచిన సమాచారాన్ని ఎప్పుడైనా డౌన్‌లోడ్ చేసుకోవచ్చు, తొలగించుకోవచ్చు."
    ),
}


class ConsentBody(BaseModel):
    profile_id: str
    purposes: list[str] = []
    granted: bool = True
    language: str = "en"


@app.get("/api/consent/notice")
def consent_notice(lang: str = "en") -> dict[str, Any]:
    """The plain-language notice, in the citizen's own language."""
    code = i18n.normalise(lang)
    return {
        "language": code,
        "notice_version": store.NOTICE_VERSION,
        "purposes": store.CONSENT_PURPOSES,
        "text": CONSENT_NOTICE.get(code, CONSENT_NOTICE["en"]),
        "rights": [
            "Access and download every fact we hold (/api/profiles/{id}/export)",
            "Erase the household entirely (DELETE /api/profiles/{id})",
            "Retention window: households older than the configured window are swept at boot",
        ],
    }


@app.post("/api/consent")
def create_consent(body: ConsentBody) -> dict[str, Any]:
    """Record or withdraw consent for a stored household."""
    if store.get_profile(body.profile_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown profile '{body.profile_id}'.")
    entry = store.record_consent(
        body.profile_id, body.purposes, granted=body.granted, language=body.language
    )
    return {"consent": entry, "history": store.list_consents(body.profile_id)}


@app.get("/api/consent/{profile_id}")
def consent_history(profile_id: str) -> dict[str, Any]:
    return {"profile_id": profile_id, "consents": store.list_consents(profile_id)}



@app.get("/api/profiles/{profile_id}/export")
def export_profile(profile_id: str) -> dict[str, Any]:
    """Right to access / portability: everything we hold, in one JSON file."""
    payload = store.export_profile(profile_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Unknown profile '{profile_id}'.")
    return payload


@app.delete("/api/profiles/{profile_id}")
def erase_profile(profile_id: str) -> dict[str, Any]:
    """Right to erasure: delete the household and everything attached to it."""
    if store.get_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown profile '{profile_id}'.")
    return store.delete_profile(profile_id)


@app.post("/api/privacy/purge", dependencies=[Depends(_require_admin)])
def purge_retention(days: Optional[int] = Query(None, ge=1, le=3650)) -> dict[str, Any]:
    """Run the retention sweep on demand (a timer does this in production)."""
    return store.purge_expired(days)


def _ics_text(value: str) -> str:
    """Escape a value for an iCalendar TEXT field (RFC 5545)."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
    )


@app.get("/api/reminders/calendar.ics")
def reminders_calendar(profile_id: Optional[str] = None) -> Response:
    """The queued deadline nudges as a phone-calendar file - the offline nudge."""
    reminders = store.list_reminders(profile_id, status="pending")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SchemeSetu//Deadline reminders//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for row in reminders:
        day = str(row["due_on"]).replace("-", "")
        lines += [
            "BEGIN:VEVENT",
            f"UID:schemesetu-{row['id']}@schemesetu",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day}",
            f"DTEND;VALUE=DATE:{day}",
            f"SUMMARY:{_ics_text(row['message'] or 'SchemeSetu: check your application')}",
            "DESCRIPTION:"
            + _ics_text(
                "Keep the documents ready and apply before the deadline. SchemeSetu is guidance, "
                "not a guarantee - confirm on the official portal."
            ),
            "BEGIN:VALARM",
            "TRIGGER:-P2D",
            "ACTION:DISPLAY",
            "DESCRIPTION:SchemeSetu deadline in 2 days",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response(
        content="\r\n".join(lines) + "\r\n",
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="schemesetu-reminders.ics"',
            "X-Reminder-Count": str(len(reminders)),
        },
    )


# --------------------------------------------------------------------------- #
# the last mile: a printable checklist the citizen carries to the office
# --------------------------------------------------------------------------- #
def _checklist_text(
    rows: list[dict[str, Any]], profile: Profile, cash_total: float, cover_total: float, lang: str
) -> str:
    lines = [
        "SCHEMESETU - APPLICATION CHECKLIST",
        f"For: {profile.name or 'this household'}",
        f"Generated: {date.today().isoformat()}",
        f"Transfers and in-kind support, per year: Rs {cash_total:,.0f}",
        f"Risk cover also unlocked (pays out only on an event): Rs {cover_total:,.0f}",
        "",
        "Carry this to the MeeSeva centre, Gram Panchayat or bank. Every scheme below was",
        "checked against the facts you gave us, and each line cites the source it came from.",
        "",
    ]
    for index, row in enumerate(rows, 1):
        local = f" / {row['name_local']}" if row.get("name_local") else ""
        cover = " - risk cover, not cash" if row["category"] in COVER_CATEGORIES else ""
        lines.append(
            f"{index}. {row['name']}{local}  [{row['verdict_label']} | {row['provenance']}]{cover}"
        )
        if row["benefit"]:
            lines.append(f"   Benefit: {row['benefit']}")
        if row["deadline"]:
            lines.append(f"   Deadline: {row['deadline']}")
        if row["documents"]:
            lines.append("   Documents to keep ready:")
            for doc in row["documents"]:
                flag = "compulsory" if doc["mandatory"] else "if available"
                how = f" - {doc['how_to_get']}" if doc["how_to_get"] else ""
                lines.append(f"     - {doc['label']} ({flag}){how}")
        if row["apply_steps"]:
            lines.append("   Steps:")
            for step_no, step in enumerate(row["apply_steps"], 1):
                lines.append(f"     {step_no}) {step}")
        if row["apply_url"]:
            lines.append(f"   Portal: {row['portal_name'] or 'official portal'} - {row['apply_url']}")
        lines.append(f"   Source: {row['source_name']} ({row['source_url']}) verified {row['verified_on']}")
        lines.append("")
    lines += [
        "This is guidance, not a guarantee. Rules were curated from public official sources on",
        "the dates shown; confirm on the official portal before you pay any fee.",
    ]
    return "\n".join(lines)


def _whatsapp_text(
    rows: list[dict[str, Any]], profile: Profile, cash_total: float, cover_total: float, lang: str
) -> str:
    """Format a clean WhatsApp-ready message for field workers and citizens."""
    header = "🏛️ *SCHEMESETU - GOVERNMENT BENEFIT NAVIGATOR*"
    if lang == "te":
        header = "🏛️ *స్కీమ్‌సేతు - మీ ప్రభుత్వ పథకాల వివరాలు*"
    elif lang == "hi":
        header = "🏛️ *स्कीमसेतु - आपकी सरकारी योजनाओं का विवरण*"

    lines = [
        header,
        f"👤 *Beneficiary:* {profile.name or 'Citizen / Household'}",
        f"💰 *Direct Cash / DBT Support:* ₹{cash_total:,.0f} / year",
    ]
    if cover_total > 0:
        lines.append(f"🛡️ *Health & Risk Cover:* ₹{cover_total:,.0f} (Insurance/Hospitalization)")
    
    lines.append(f"\n📋 *Eligible Schemes ({len(rows)}):*")
    for index, row in enumerate(rows[:6], 1):
        local = f" ({row['name_local']})" if row.get("name_local") else ""
        benefit = f" - {row['benefit']}" if row.get("benefit") else ""
        lines.append(f"{index}. *{row['name']}*{local}{benefit}")
        if row.get("apply_url"):
            lines.append(f"   🔗 {row['apply_url']}")
    
    mand_docs = sorted({d["label"] for row in rows for d in row.get("documents", []) if d.get("mandatory")})
    if mand_docs:
        lines.append("\n📄 *Documents to Keep Ready:*")
        for doc in mand_docs[:6]:
            lines.append(f"  • {doc}")
            
    lines += [
        "\nℹ️ *Guidance Only:* Verified against official portal criteria. Never share OTP or Aadhaar numbers.",
        "🌐 *MeeSeva Telangana Portal:* https://meeseva.telangana.gov.in (Helpline: 1100)",
    ]
    return "\n".join(lines)


@app.get("/api/checklist/{profile_id}")
def checklist(profile_id: str, lang: str = "en") -> dict[str, Any]:
    """Printable, citable checklist of everything worth applying for."""
    bundle = graph_store.get_bundle()
    profile = _load_profile(None, profile_id)
    pairs = [(s, engine.evaluate_scheme(s, profile, bundle.categories)) for s in bundle.schemes]
    matches = engine.rank_matches([m for _, m in pairs])

    rows: list[dict[str, Any]] = []
    for scheme, match in pairs:
        if match.verdict not in {"likely_eligible", "possible"}:
            continue
        rows.append(
            {
                "scheme_id": scheme.id,
                "name": scheme.name,
                "category": scheme.category,
                "name_local": scheme.name_local.get(i18n.normalise(lang), ""),
                "verdict": match.verdict,
                "verdict_label": i18n.verdict_label(match.verdict, lang),
                "confidence": match.confidence,
                "benefit": scheme.benefit,
                "benefit_value_inr": scheme.benefit_value_inr,
                "portal_name": scheme.portal_name,
                "apply_url": scheme.apply_url,
                "deadline": engine.describe_deadline(scheme.deadline),
                "apply_steps": scheme.apply_steps,
                "documents": [
                    {
                        "label": doc.label,
                        "mandatory": doc.mandatory,
                        "how_to_get": doc.how_to_get,
                        "note": doc.note,
                    }
                    for doc in scheme.documents
                ],
                "provenance": scheme.provenance,
                "verified_on": scheme.verified_on,
                "source_name": scheme.source_name,
                "source_url": scheme.source_url,
            }
        )
    rows.sort(key=lambda row: (-row["benefit_value_inr"], row["name"]))
    cash_total = sum(
        row["benefit_value_inr"] for row in rows if row["category"] not in COVER_CATEGORIES
    )
    cover_total = sum(
        row["benefit_value_inr"] for row in rows if row["category"] in COVER_CATEGORIES
    )
    mandatory_docs = sorted({d["label"] for row in rows for d in row["documents"] if d["mandatory"]})
    plain_text = _checklist_text(rows, profile, cash_total, cover_total, lang)
    wa_text = _whatsapp_text(rows, profile, cash_total, cover_total, lang)
    wa_url = f"https://wa.me/?text={urllib.parse.quote(wa_text)}"
    op_token = f"TS-MEESEVA-{profile_id[:8].upper()}" if profile_id else "TS-MEESEVA-DEMO"

    return {
        "profile_id": profile_id,
        "operator_token": op_token,
        "generated_on": date.today().isoformat(),
        "headline": engine.match_summary(matches)["headline"],
        "estimated_yearly_benefit_inr": cash_total,
        "estimated_cover_inr": cover_total,
        "estimated_total_inr": cash_total + cover_total,
        "scheme_count": len(rows),
        "mandatory_documents": mandatory_docs,
        "schemes": rows,
        "text": plain_text,
        "whatsapp_text": wa_text,
        "whatsapp_url": wa_url,
        "guardrail": engine.GUARDRAIL_WORDING,
        "note": (
            "Same deterministic verdicts as the screen - just laid out to be printed or "
            "forwarded on WhatsApp. Nothing was recomputed by a model."
        ),
    }


OPERATORS = [
    "eq", "ne", "in", "not_in", "gt", "gte", "lt", "lte",
    "between", "true", "false", "exists", "class_between", "class_gte", "class_lt",
]


def _rule_rows(bundle: graph_store.GraphBundle) -> list[dict[str, Any]]:
    rows = []
    for scheme in bundle.schemes:
        rows.append(
            {
                "scheme_id": scheme.id,
                "scheme_name": scheme.name,
                "category": scheme.category,
                "level": scheme.level,
                "provenance": scheme.provenance,
                "verified_on": scheme.verified_on,
                "source_name": scheme.source_name,
                "source_url": scheme.source_url,
                "rules": [
                    {
                        "id": rule.id,
                        "field": rule.field,
                        "field_label": engine.field_label(rule.field),
                        "op": rule.op,
                        "value": rule.value,
                        "text": rule.text,
                        "hard": rule.hard,
                        "weight": rule.weight,
                        "source_note": rule.source_note,
                    }
                    for rule in scheme.rules
                ],
            }
        )
    return rows


def _default_profile() -> Profile:
    """A representative household, so the studio always has something to show."""
    stored = store.list_profiles(limit=1)
    if stored:
        return Profile(**stored[0]["facts"])
    return Profile(
        name="Demo household",
        state=settings.state_focus,
        age=45,
        gender="female",
        income_band="low",
        annual_income_inr=90000,
        occupation="daily_wage",
        is_unorganised_worker=True,
        has_ration_card=True,
        has_bank_account=True,
        is_rural=True,
        family_size=4,
        class_level="Class 9",
    )


@app.get("/api/rule-studio")
def rule_studio() -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    return {
        "schemes": _rule_rows(bundle),
        "operators": OPERATORS,
        "graph": graph_store.graph_stats(bundle),
        "note": (
            "Change an operator, threshold or weight and press Simulate. The verdict is "
            "recomputed by the same deterministic engine the citizens use, and the impact is "
            "measured across every stored household."
        ),
    }


def _overrides_dict(body: StudioBody) -> dict[str, dict[str, Any]]:
    return {rule_id: patch.model_dump(exclude_none=True) for rule_id, patch in body.overrides.items()}


@app.post("/api/rule-studio/simulate")
def rule_studio_simulate(body: StudioBody) -> dict[str, Any]:
    bundle = graph_store.get_bundle()
    scheme = bundle.scheme(body.scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Unknown scheme '{body.scheme_id}'.")
    overrides = _overrides_dict(body)
    if not overrides:
        raise HTTPException(status_code=422, detail="Send at least one rule override.")
    patched, diff = engine.apply_rule_overrides(scheme, overrides)
    profile = _load_profile(None, body.profile_id) if body.profile_id else _default_profile()

    before = engine.evaluate_scheme(scheme, profile, bundle.categories)
    after = engine.evaluate_scheme(patched, profile, bundle.categories)

    impact = []
    for row in store.list_profiles(limit=50):
        stored = Profile(**row["facts"])
        b = engine.evaluate_scheme(scheme, stored, bundle.categories)
        a = engine.evaluate_scheme(patched, stored, bundle.categories)
        impact.append(
            {
                "profile_id": row["id"],
                "label": row["label"],
                "before": b.verdict,
                "after": a.verdict,
                "changed": b.verdict != a.verdict,
                "before_confidence": b.confidence,
                "after_confidence": a.confidence,
            }
        )
    return {
        "scheme_id": scheme.id,
        "scheme_name": scheme.name,
        "diff": diff,
        "profile_id": body.profile_id,
        "profile_label": "this household" if body.profile_id else "the demo household",
        "before": _localise_match(before, body.language),
        "after": _localise_match(after, body.language),
        "changed": before.verdict != after.verdict,
        "impact": impact,
        "changed_count": sum(1 for row in impact if row["changed"]),
        "verdicts": engine.VERDICT_LABELS,
        "note": "Nothing was written to disk yet - press Apply to persist this rule change.",
    }


@app.post("/api/rule-studio/apply", dependencies=[Depends(_require_admin)])
def rule_studio_apply(body: StudioBody) -> dict[str, Any]:
    """Persist a rule change into ``data/schemes.json`` (with a ``.json.bak`` backup).

    The edited scheme is re-tagged ``INFERRED``: a human just changed a rule the
    official source stated otherwise, and saying so is the honest thing to do.
    """
    bundle = graph_store.get_bundle()
    scheme = bundle.scheme(body.scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail=f"Unknown scheme '{body.scheme_id}'.")
    overrides = _overrides_dict(body)
    if not overrides:
        raise HTTPException(status_code=422, detail="Send at least one rule override.")

    path = settings.schemes_path
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read {path}: {exc}") from exc

    path.with_suffix(".json.bak").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    touched: list[dict[str, Any]] = []
    original_provenance = scheme.provenance
    for entry in raw.get("schemes", []):
        if entry.get("id") != body.scheme_id:
            continue
        for rule in entry.get("rules", []):
            patch = overrides.get(rule.get("id"))
            if patch:
                rule.update(patch)
                touched.append({"rule_id": rule.get("id"), "changed": patch})
        entry["provenance"] = "INFERRED"
        entry["edited_on"] = date.today().isoformat()
        entry["edited_by"] = "Rule Studio (hackathon demo)"
        entry["provenance_note"] = (
            f"Rule edited live in Rule Studio on {date.today().isoformat()}; "
            f"was {original_provenance} before the edit."
        )
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    graph_store.invalidate()
    refreshed = graph_store.get_bundle()
    updated = refreshed.scheme(body.scheme_id)
    return {
        "applied": touched,
        "backup": str(path.with_suffix(".json.bak")),
        "scheme": _scheme_payload(updated, body.language) if updated else None,
        "graph": graph_store.graph_stats(refreshed),
        "note": "Written to disk, graph reloaded, provenance re-tagged as INFERRED.",
    }


# --------------------------------------------------------------------------- #
# the UI (same origin, no build step)
# --------------------------------------------------------------------------- #
if FRONTEND_DIR.exists():

    @app.get("/sw.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        """Serve SW from root so its scope covers the entire origin."""
        return FileResponse(
            str(FRONTEND_DIR / "sw.js"),
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
        )

    @app.get("/manifest.json", include_in_schema=False)
    def manifest() -> FileResponse:
        return FileResponse(
            str(FRONTEND_DIR / "manifest.json"),
            media_type="application/manifest+json",
        )

    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))
