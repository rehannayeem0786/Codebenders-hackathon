"""Tests for the store (SQLite) and the HTTP API surface."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import store  # noqa: E402
from backend.app.models import Profile  # noqa: E402


def test_store_round_trip_scrubs_and_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "settings", type("S", (), {"db_path": tmp_path / "app.db"})())
    profile = Profile(state="Telangana", age=58, is_widow=True, notes="call 9876543210")
    pid = store.save_profile(profile, transcript="aadhaar 1234 5678 9012", sources={"age": "rules"})
    stored = store.get_profile(pid)
    assert stored is not None
    assert stored["facts"]["age"] == 58
    assert "1234 5678 9012" not in stored["transcript"]
    assert store.profile_object(pid).age == 58
    assert store.list_profiles()[0]["label"].startswith("58y")
    assert store.stats()["profiles"] == 1


def test_reminders_are_planned_from_dated_deadlines(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "settings", type("S", (), {"db_path": tmp_path / "app.db"})())
    from backend.app import graph_store
    from backend.app import rule_engine as eng

    bundle = graph_store.get_bundle()
    profile = Profile(
        state="Telangana",
        age=16,
        is_student=True,
        class_level="Class 10",
        social_category="sc",
        gender="male",
        annual_income_inr=120000,
        income_band="low",
        education_level="class_8",
    )
    pairs = [(s, eng.evaluate_scheme(s, profile, bundle.categories)) for s in bundle.schemes]
    created = store.plan_reminders("p1", pairs)
    assert created, "the student should have at least one dated deadline"
    again = store.plan_reminders("p1", pairs)
    assert again == [], "planning twice must be idempotent"
    assert store.list_reminders("p1")


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)


def test_health_reports_providers_graph_and_guardrails(client):
    data = client.get("/api/health").json()
    assert data["app"] == "SchemeSetu"
    assert data["graph"]["schemes"] >= 20
    assert data["guardrails"]["pii_redaction"] is True
    assert "fallback_chain" in data["llm"]
    assert data["engine"]["wording"]


def test_intake_endpoint_returns_explained_matches(client):
    data = client.post(
        "/api/intake",
        json={
            "text": (
                "I am 58, a widow in Warangal. White ration card and 2 acres of land. "
                "My aadhaar is 1234 5678 9012."
            ),
            "language": "en",
            "save": False,
            "use_llm": False,
        },
    ).json()
    assert len(data["matches"]) >= 20
    assert all(m["why"] for m in data["matches"])
    assert "XXXX" in data["intake"]["transcript"]
    assert any(m["verdict"] == "likely_eligible" for m in data["matches"])
    assert data["next_questions"]


def test_rule_studio_simulate_moves_a_verdict(client):
    data = client.post(
        "/api/rule-studio/simulate",
        json={"scheme_id": "ts-aasara-oldage", "overrides": {"aasara.age": {"value": 70}}},
    ).json()
    assert data["diff"]["aasara.age"]["after"]["value"] == 70
    assert data["after"]["verdict"] in {"not_eligible", "likely_eligible", "possible", "needs_info"}


def test_graph_endpoints_answer_for_a_scheme_and_a_search(client):
    detail = client.get("/api/schemes/ts-aasara-oldage").json()
    assert detail["rule_count"] >= 5
    assert detail["graph"]["found"] is True
    found = client.get("/api/graph/search", params={"q": "aarogyasri"}).json()["results"]
    assert any(node["kind"] == "scheme" for node in found)


def test_i18n_payload_localises_verdicts_and_questions(client):
    payload = client.get("/api/i18n/te").json()
    assert payload["verdicts"]["likely_eligible"] == "అర్హత ఉండే అవకాశం"
    assert "వయస్సు" in payload["field_questions"]["age"]


def test_voice_endpoint_explains_itself_when_stt_is_off(client, monkeypatch):
    from backend.app import llm

    monkeypatch.setattr(llm, "transcribe", lambda *a, **k: None)
    response = client.post(
        "/api/voice",
        files={"file": ("voice.webm", b"RIFFfake", "audio/webm")},
        params={"language": "te"},
    )
    assert response.status_code == 503
    assert "typing still works" in response.json()["detail"]


def test_checklist_includes_whatsapp_url_and_operator_token(client):
    pid = store.save_profile(Profile(state="Telangana", age=58, is_widow=True, has_ration_card=True))
    data = client.get(f"/api/checklist/{pid}?lang=te").json()
    assert "whatsapp_url" in data
    assert "https://wa.me/?text=" in data["whatsapp_url"]
    assert "operator_token" in data
    assert "TS-MEESEVA-" in data["operator_token"]
    assert "whatsapp_text" in data
    assert "SCHEMESETU" in data["whatsapp_text"] or "స్కీమ్‌సేతు" in data["whatsapp_text"]


def test_graphify_knowledge_graph_merged_with_evidence(client):
    health = client.get("/api/health").json()
    assert health["graph"]["graphify"]["imported"] is True
    assert health["graph"]["graphify"]["nodes"] > 50
    assert health["graph"]["graphify"]["bridged"] > 50
    assert "EXTRACTED" in health["graph"]["graphify"]["by_provenance"]



def test_service_worker_route_returns_js(client):
    """The /sw.js route must serve the service worker with correct headers."""
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("content-type", "")
    assert "Service-Worker-Allowed" in r.headers
    body = r.text
    assert "CACHE_NAME" in body
    assert "schemesetu-v1" in body


def test_manifest_route_returns_json(client):
    """The /manifest.json route must serve a valid PWA manifest."""
    r = client.get("/manifest.json")
    assert r.status_code == 200
    body = r.json()
    assert body["short_name"] == "SchemeSetu"
    assert body["display"] == "standalone"
    assert body["theme_color"] == "#3b82f6"
    assert any(icon["type"] == "image/svg+xml" for icon in body.get("icons", []))


def test_favicon_svg_served(client):
    """The favicon SVG must be accessible from /static/favicon.svg."""
    r = client.get("/static/favicon.svg")
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "").lower() or "xml" in r.headers.get("content-type", "").lower()
    assert "<svg" in r.text


def test_index_html_has_pwa_meta_tags(client):
    """index.html must include PWA meta tags for installability."""
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    assert 'rel="manifest"' in body
    assert 'rel="icon"' in body
    assert 'name="theme-color"' in body
    assert "apple-mobile-web-app-capable" in body
    assert "btn-theme-toggle" in body
