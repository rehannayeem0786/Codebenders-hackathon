"""Data-rights tests: consent, access, erasure, retention, checklist, calendar.

These are the tests that answer "you redact IDs - but what rights does the
citizen actually have over what you kept?" (DPDP Act 2023, and a fair question
from any judge).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import store  # noqa: E402
from backend.app.models import Application, Profile  # noqa: E402

RICH_TEXT = (
    "I am 58 years old, a widow in Warangal. We have a white ration card and 2 acres of land. "
    "My son studies in class 9 and we have a bank account. Household income is about 90000 a year."
)


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """A throwaway database, so erasure tests never touch the demo data."""
    monkeypatch.setattr(
        store,
        "settings",
        type("S", (), {"db_path": tmp_path / "app.db", "data_retention_days": 90})(),
    )
    return tmp_path / "app.db"


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from backend.app.main import app

    return TestClient(app)


def _save(**facts) -> str:
    return store.save_profile(Profile(state="Telangana", **facts))


# --------------------------------------------------------------------------- #
# store level
# --------------------------------------------------------------------------- #
def test_consent_is_recorded_with_purposes_language_and_version(isolated_db):
    pid = _save(age=58, is_widow=True)
    entry = store.record_consent(pid, ["eligibility_matching"], language="te")
    assert entry["granted"] is True
    assert entry["purposes"] == ["eligibility_matching"]
    assert entry["notice_version"] == store.NOTICE_VERSION

    store.record_consent(pid, granted=False, language="te")
    history = store.list_consents(pid)
    assert [row["granted"] for row in history] == [False, True]
    assert history[-1]["language"] == "te"


def test_unknown_consent_purposes_are_dropped_not_stored(isolated_db):
    pid = _save(age=30)
    entry = store.record_consent(pid, ["sell_to_broker", "eligibility_matching"])
    assert entry["purposes"] == ["eligibility_matching"]


def test_export_holds_everything_and_no_identifiers(isolated_db):
    pid = store.save_profile(
        Profile(state="Telangana", age=58, is_widow=True, notes="aadhaar 1234 5678 9012"),
        transcript="my aadhaar is 1234 5678 9012",
    )
    store.upsert_application(
        Application(profile_id=pid, scheme_id="ts-aasara-widow", scheme_name="Aasara")
    )
    store.record_consent(pid)

    payload = store.export_profile(pid)
    assert payload is not None
    assert payload["profile"]["facts"]["age"] == 58
    assert len(payload["applications"]) == 1
    assert payload["consents"]

    blob = json.dumps(payload, ensure_ascii=False)
    assert "1234 5678 9012" not in blob, "the export must never contain an ID we redacted"
    assert store.export_profile("does-not-exist") is None


def test_erasure_removes_facts_children_and_keeps_one_tombstone(isolated_db):
    pid = _save(age=58, is_widow=True)
    store.upsert_application(Application(profile_id=pid, scheme_id="x", scheme_name="X"))
    store.record_consent(pid)

    result = store.delete_profile(pid)
    assert result["deleted"]["profiles"] == 1
    assert result["deleted"]["consents"] == 1
    assert store.get_profile(pid) is None
    assert store.list_applications(pid) == []
    assert store.list_reminders(pid) == []
    assert store.list_consents(pid) == []

    leftovers = store.list_audit(pid)
    assert [entry["event"] for entry in leftovers] == ["profile_erased"]
    assert "age" not in json.dumps(leftovers[0]["payload"]), "the tombstone must hold no facts"


def test_retention_sweep_erases_only_households_past_the_window(isolated_db):
    old = _save(age=40)
    fresh = _save(age=41)
    stale = (datetime.now() - timedelta(days=200)).replace(microsecond=0).isoformat()
    with store.connect() as conn:
        conn.execute("UPDATE profiles SET created_at = ? WHERE id = ?", (stale, old))

    swept = store.purge_expired(90)
    assert swept["erased_profiles"] == [old]
    assert store.get_profile(old) is None
    assert store.get_profile(fresh) is not None


# --------------------------------------------------------------------------- #
# HTTP level
# --------------------------------------------------------------------------- #
def test_consent_notice_speaks_all_three_languages(client):
    for lang in ("en", "hi", "te"):
        data = client.get(f"/api/consent/notice?lang={lang}").json()
        assert len(data["text"]) > 80, f"notice too short for {lang}"
        assert data["notice_version"] == store.NOTICE_VERSION
        assert "eligibility_matching" in data["purposes"]
        assert data["rights"]


def test_intake_records_consent_then_export_and_erase_round_trip(client):
    intake = client.post(
        "/api/intake",
        json={"text": RICH_TEXT, "language": "en", "save": True, "use_llm": False},
    ).json()
    pid = intake["profile_id"]
    assert pid, "a saved intake must return a profile id"
    assert intake["consent"]["granted"] is True
    assert intake["consent"]["purposes"] == store.CONSENT_PURPOSES
    assert client.get(f"/api/consent/{pid}").json()["consents"]

    exported = client.get(f"/api/profiles/{pid}/export").json()
    assert exported["profile"]["facts"]["age"] == 58
    assert client.get("/api/profiles/nope/export").status_code == 404

    erased = client.delete(f"/api/profiles/{pid}").json()
    assert erased["deleted"]["profiles"] == 1
    assert client.get(f"/api/profiles/{pid}").status_code == 404
    assert client.delete(f"/api/profiles/{pid}").status_code == 404


def test_consent_can_be_withdrawn_over_http(client):
    intake = client.post(
        "/api/intake",
        json={"text": RICH_TEXT, "language": "te", "save": True, "use_llm": False},
    ).json()
    pid = intake["profile_id"]
    withdrawal = client.post(
        "/api/consent",
        json={"profile_id": pid, "granted": False, "language": "te"},
    ).json()
    assert withdrawal["consent"]["granted"] is False
    assert withdrawal["consent"]["language"] == "te"
    assert client.post("/api/consent", json={"profile_id": "ghost"}).status_code == 404
    client.delete(f"/api/profiles/{pid}")


def test_checklist_is_ranked_printable_and_cited(client):
    intake = client.post(
        "/api/intake",
        json={"text": RICH_TEXT, "language": "en", "save": True, "use_llm": False},
    ).json()
    pid = intake["profile_id"]
    data = client.get(f"/api/checklist/{pid}?lang=en").json()

    assert data["scheme_count"] >= 2, "a widow with land should unlock several schemes"

    # Cash and risk cover are reported separately and must never be merged.
    assert data["estimated_total_inr"] == (
        data["estimated_yearly_benefit_inr"] + data["estimated_cover_inr"]
    )
    assert data["estimated_total_inr"] > 0
    assert "Transfers and in-kind support, per year" in data["text"]
    assert "Risk cover also unlocked" in data["text"]
    assert "SCHEMESETU - APPLICATION CHECKLIST" in data["text"]
    assert "not a guarantee" in data["text"]

    values = [row["benefit_value_inr"] for row in data["schemes"]]
    assert values == sorted(values, reverse=True), "checklist must lead with the biggest benefit"
    assert all(row["source_url"] and row["verified_on"] for row in data["schemes"])
    assert data["mandatory_documents"]
    assert client.get("/api/checklist/ghost").status_code == 404
    client.delete(f"/api/profiles/{pid}")


def test_calendar_export_is_valid_ics(client):
    # A student household: the existing suite proves it gets dated deadlines.
    intake = client.post(
        "/api/intake",
        json={
            "text": (
                "I am 16 years old and I study in class 10 in Hyderabad. We are a scheduled "
                "caste family with a ration card and my father's income is about 1.2 lakh a year."
            ),
            "language": "en",
            "save": True,
            "use_llm": False,
            "plan_reminders": True,
            "form": {
                "state": "Telangana",
                "social_category": "sc",
                "is_student": True,
                "class_level": "Class 10",
                "gender": "male",
                "annual_income_inr": 120000,
                "income_band": "low",
                "education_level": "class_8",
            },
        },
    ).json()
    pid = intake["profile_id"]
    reminders = client.get(f"/api/reminders?profile_id={pid}").json()["reminders"]
    assert reminders, "the student household should have dated deadlines to queue"

    response = client.get(f"/api/reminders/calendar.ics?profile_id={pid}")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert response.headers["content-disposition"].endswith('.ics"')
    body = response.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert body.rstrip().endswith("END:VCALENDAR")
    assert body.count("BEGIN:VEVENT") == len(reminders)
    assert body.count("BEGIN:VEVENT") == body.count("END:VEVENT")
    assert "DTSTART;VALUE=DATE:" in body
    client.delete(f"/api/profiles/{pid}")
