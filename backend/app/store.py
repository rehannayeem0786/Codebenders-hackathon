"""SQLite persistence: profiles, applications, reminders, audit trail.

Deliberately dependency-free (stdlib ``sqlite3``) so the demo runs on any
machine. Only redacted facts are ever written: the intake layer scrubs before
anything reaches this module, and :func:`save_profile` scrubs again on the way
in, so a mistake upstream cannot leak an ID into the database file.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any, Iterator, Optional

from . import pii
from .config import settings
from .models import Application, Profile, Reminder

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    name TEXT,
    transcript TEXT,
    facts TEXT NOT NULL,
    sources TEXT,
    meta TEXT
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    scheme_id TEXT NOT NULL,
    scheme_name TEXT,
    status TEXT NOT NULL DEFAULT 'not_started',
    notes TEXT DEFAULT '',
    deadline TEXT,
    documents_ready TEXT DEFAULT '[]',
    reference_no TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_reminder_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_unique ON applications(profile_id, scheme_id);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER,
    profile_id TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'deadline',
    due_on TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'in_app',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    event TEXT NOT NULL,
    profile_id TEXT,
    payload TEXT
);
CREATE TABLE IF NOT EXISTS consent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    at TEXT NOT NULL,
    purposes TEXT NOT NULL,
    granted INTEGER NOT NULL DEFAULT 1,
    language TEXT DEFAULT 'en',
    notice_version TEXT DEFAULT 'v1'
);
"""


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open the database, creating the file and schema on first use."""
    path = settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


# --------------------------------------------------------------------------- #
# profiles
# --------------------------------------------------------------------------- #
def save_profile(
    profile: Profile,
    *,
    transcript: str = "",
    sources: Optional[dict[str, str]] = None,
    meta: Optional[dict[str, Any]] = None,
    profile_id: Optional[str] = None,
) -> str:
    """Insert or update a profile and return its id."""
    clean_facts, report = pii.sanitize_profile(profile.known())
    safe_transcript = pii.redact_text(transcript or "")
    pid = profile_id or uuid.uuid4().hex[:12]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO profiles (id, created_at, name, transcript, facts, sources, meta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                transcript=excluded.transcript,
                facts=excluded.facts,
                sources=excluded.sources,
                meta=excluded.meta
            """,
            (
                pid,
                _now(),
                clean_facts.get("name"),
                safe_transcript,
                _json(clean_facts),
                _json(sources or {}),
                _json({**(meta or {}), "guardrail": report}),
            ),
        )
        _audit(conn, "profile_saved", pid, {"fields": sorted(clean_facts)})
    return pid


def get_profile(profile_id: str) -> Optional[dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "name": row["name"],
        "transcript": row["transcript"],
        "facts": _loads(row["facts"], {}),
        "sources": _loads(row["sources"], {}),
        "meta": _loads(row["meta"], {}),
    }


def profile_object(profile_id: str) -> Optional[Profile]:
    stored = get_profile(profile_id)
    return Profile(**stored["facts"]) if stored else None


def list_profiles(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, name, facts FROM profiles ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        facts = _loads(row["facts"], {})
        out.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "name": row["name"],
                "label": _profile_label(facts),
                "fact_count": len(facts),
                "facts": facts,
            }
        )
    return out


def _profile_label(facts: dict[str, Any]) -> str:
    bits = []
    if facts.get("age"):
        bits.append(f"{facts['age']}y")
    if facts.get("gender"):
        bits.append(str(facts["gender"]))
    if facts.get("district"):
        bits.append(str(facts["district"]))
    if facts.get("occupation"):
        bits.append(str(facts["occupation"]).replace("_", " "))
    if facts.get("income_band"):
        bits.append(str(facts["income_band"]))
    return " - ".join(bits) or "incomplete profile"


# --------------------------------------------------------------------------- #
# applications
# --------------------------------------------------------------------------- #
def upsert_application(app: Application) -> int:
    """Create or update one application row; returns its id."""
    now = _now()
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM applications WHERE profile_id = ? AND scheme_id = ?",
            (app.profile_id, app.scheme_id),
        ).fetchone()
        if row is None:
            cursor = conn.execute(
                """
                INSERT INTO applications
                    (profile_id, scheme_id, scheme_name, status, notes, deadline,
                     documents_ready, reference_no, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app.profile_id,
                    app.scheme_id,
                    app.scheme_name,
                    app.status,
                    app.notes,
                    app.deadline,
                    _json(app.documents_ready),
                    app.reference_no,
                    now,
                    now,
                ),
            )
            app_id = int(cursor.lastrowid or 0)
            _audit(conn, "application_created", app.profile_id, {"scheme_id": app.scheme_id, "id": app_id})
            return app_id
        app_id = int(row["id"])
        conn.execute(
            """
            UPDATE applications
               SET status = ?, notes = ?, deadline = ?, documents_ready = ?,
                   reference_no = ?, scheme_name = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                app.status,
                app.notes,
                app.deadline,
                _json(app.documents_ready),
                app.reference_no,
                app.scheme_name,
                now,
                app_id,
            ),
        )
        _audit(conn, "application_updated", app.profile_id, {"scheme_id": app.scheme_id, "id": app_id, "status": app.status})
    return app_id


def list_applications(profile_id: Optional[str] = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM applications"
    params: tuple[Any, ...] = ()
    if profile_id:
        query += " WHERE profile_id = ?"
        params = (profile_id,)
    query += " ORDER BY updated_at DESC"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_app_row(row) for row in rows]


def _app_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "profile_id": row["profile_id"],
        "scheme_id": row["scheme_id"],
        "scheme_name": row["scheme_name"],
        "status": row["status"],
        "notes": row["notes"],
        "deadline": row["deadline"],
        "documents_ready": _loads(row["documents_ready"], []),
        "reference_no": row["reference_no"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# --------------------------------------------------------------------------- #
# reminders
# --------------------------------------------------------------------------- #
def _deadline_date(deadline: Any, today: Optional[date] = None) -> Optional[date]:
    """Next calendar date a dated deadline falls on (rolling ones return None)."""
    today = today or date.today()
    if deadline is None:
        return None
    kind = getattr(deadline, "type", "rolling")
    raw = getattr(deadline, "month_day", None) if kind in {"annual", "window"} else None
    if not raw or "-" not in raw:
        return None
    month, day = raw.split("-")[:2]
    for year in (today.year, today.year + 1):
        try:
            candidate = date(year, int(month), int(day))
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def add_reminder(reminder: Reminder) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO reminders
                (application_id, profile_id, kind, due_on, message, channel, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reminder.application_id,
                reminder.profile_id,
                reminder.kind,
                reminder.due_on,
                reminder.message,
                reminder.channel,
                reminder.status,
                _now(),
            ),
        )
        _audit(conn, "reminder_created", reminder.profile_id, {"due_on": reminder.due_on, "kind": reminder.kind})
        return int(cursor.lastrowid or 0)


def list_reminders(profile_id: Optional[str] = None, status: Optional[str] = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM reminders"
    clauses: list[str] = []
    params: list[Any] = []
    if profile_id:
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY due_on ASC"
    with connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def due_reminders(on: Optional[date] = None, window_days: int = 7) -> list[dict[str, Any]]:
    """Pending reminders due within the window - what a WhatsApp/SMS nudge would send."""
    on = on or date.today()
    horizon = (on + timedelta(days=window_days)).isoformat()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE status = 'pending' AND due_on <= ? ORDER BY due_on ASC",
            (horizon,),
        ).fetchall()
    return [dict(row) for row in rows]


def complete_reminder(reminder_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("UPDATE reminders SET status = 'done' WHERE id = ?", (reminder_id,))
        return cursor.rowcount > 0


def plan_reminders(
    profile_id: str,
    pairs: list[tuple[Any, Any]],
    *,
    days_before: int = 10,
) -> list[dict[str, Any]]:
    """Create deadline reminders for matches. ``pairs`` is a list of ``(scheme, match)``.

    Deterministic and idempotent: the same profile + scheme + date is never
    queued twice, and schemes with rolling deadlines are skipped.
    """
    created: list[dict[str, Any]] = []
    today = date.today()
    existing = {(r["profile_id"], r["due_on"], r["message"]) for r in list_reminders(profile_id)}
    for scheme, match in pairs:
        if getattr(match, "verdict", "") not in {"likely_eligible", "possible"}:
            continue
        due = _deadline_date(getattr(scheme, "deadline", None), today)
        if due is None:
            continue
        remind_on = max(due - timedelta(days=days_before), today)
        message = (
            f"{scheme.name}: keep the documents ready and apply before "
            f"{due.strftime('%d %b %Y')}."
        )
        if (profile_id, remind_on.isoformat(), message) in existing:
            continue
        reminder_id = add_reminder(
            Reminder(
                profile_id=profile_id,
                kind="deadline",
                due_on=remind_on.isoformat(),
                message=message,
                channel="in_app",
            )
        )
        existing.add((profile_id, remind_on.isoformat(), message))
        created.append(
            {
                "id": reminder_id,
                "profile_id": profile_id,
                "scheme_id": scheme.id,
                "scheme_name": scheme.name,
                "due_on": remind_on.isoformat(),
                "deadline_on": due.isoformat(),
                "message": message,
            }
        )
    return created


# --------------------------------------------------------------------------- #
# audit trail
# --------------------------------------------------------------------------- #
def _audit(
    conn: sqlite3.Connection, event: str, profile_id: Optional[str], payload: dict[str, Any]
) -> None:
    conn.execute(
        "INSERT INTO audit (at, event, profile_id, payload) VALUES (?, ?, ?, ?)",
        (_now(), event, profile_id, _json(payload)),
    )


def list_audit(profile_id: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
    query = "SELECT * FROM audit"
    params: tuple[Any, ...] = ()
    if profile_id:
        query += " WHERE profile_id = ?"
        params = (profile_id,)
    query += " ORDER BY id DESC LIMIT ?"
    with connect() as conn:
        rows = conn.execute(query, params + (limit,)).fetchall()
    return [
        {
            "id": row["id"],
            "at": row["at"],
            "event": row["event"],
            "profile_id": row["profile_id"],
            "payload": _loads(row["payload"], {}),
        }
        for row in rows
    ]


def _retention_days() -> int:
    """Retention window, tolerant of test doubles that stub only ``db_path``."""
    return int(getattr(settings, "data_retention_days", 90) or 90)


def stats() -> dict[str, Any]:
    with connect() as conn:
        counts = {
            "profiles": conn.execute("SELECT COUNT(*) AS c FROM profiles").fetchone()["c"],
            "applications": conn.execute("SELECT COUNT(*) AS c FROM applications").fetchone()["c"],
            "reminders": conn.execute("SELECT COUNT(*) AS c FROM reminders").fetchone()["c"],
            "reminders_pending": conn.execute(
                "SELECT COUNT(*) AS c FROM reminders WHERE status = 'pending'"
            ).fetchone()["c"],
            "audit_rows": conn.execute("SELECT COUNT(*) AS c FROM audit").fetchone()["c"],
            "consents": conn.execute("SELECT COUNT(*) AS c FROM consent").fetchone()["c"],
        }
    return {
        **counts,
        "db_path": str(settings.db_path),
        "retention_days": _retention_days(),
        "note": (
            "Stores redacted facts only. Personal data is deleted on request and by the "
            f"{_retention_days()}-day retention sweep (DPDP Act 2023)."
        ),
    }


# --------------------------------------------------------------------------- #
# data rights (DPDP Act 2023): consent, access/portability, erasure, retention
# --------------------------------------------------------------------------- #
# PS5's guardrail says do not collect sensitive IDs. The obvious next question
# is "what rights does the citizen have over what you *did* collect?" - so
# consent, export and erasure are implemented here, not just promised in a slide.
CONSENT_PURPOSES = [
    "eligibility_matching",
    "document_guidance",
    "deadline_reminders",
    "local_language_explanation",
]

NOTICE_VERSION = "v1"


def record_consent(
    profile_id: str,
    purposes: Optional[list[str]] = None,
    *,
    granted: bool = True,
    language: str = "en",
) -> dict[str, Any]:
    """Log what the citizen agreed to, in which language, under which notice."""
    allowed = [p for p in (purposes or CONSENT_PURPOSES) if p in CONSENT_PURPOSES] or CONSENT_PURPOSES
    stamp = _now()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO consent (profile_id, at, purposes, granted, language, notice_version)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (profile_id, stamp, _json(allowed), 1 if granted else 0, language, NOTICE_VERSION),
        )
        _audit(
            conn,
            "consent_recorded" if granted else "consent_withdrawn",
            profile_id,
            {"purposes": allowed, "notice_version": NOTICE_VERSION, "language": language},
        )
        return {
            "id": int(cursor.lastrowid or 0),
            "profile_id": profile_id,
            "at": stamp,
            "purposes": allowed,
            "granted": bool(granted),
            "language": language,
            "notice_version": NOTICE_VERSION,
        }


def list_consents(profile_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM consent WHERE profile_id = ? ORDER BY id DESC", (profile_id,)
        ).fetchall()
    return [
        {
            "id": row["id"],
            "profile_id": row["profile_id"],
            "at": row["at"],
            "purposes": _loads(row["purposes"], []),
            "granted": bool(row["granted"]),
            "language": row["language"],
            "notice_version": row["notice_version"],
        }
        for row in rows
    ]


def export_profile(profile_id: str) -> Optional[dict[str, Any]]:
    """Everything we hold about one household, in one machine-readable file."""
    stored = get_profile(profile_id)
    if stored is None:
        return None
    return {
        "format": "SchemeSetu data export - right to access / portability (DPDP Act 2023)",
        "exported_at": _now(),
        "profile": stored,
        "applications": list_applications(profile_id),
        "reminders": list_reminders(profile_id),
        "consents": list_consents(profile_id),
        "audit": list_audit(profile_id, limit=200),
        "note": (
            "These are the redacted facts the engine used. Aadhaar, PAN, OTP and bank-account "
            "numbers were never collected, so they cannot appear here. Erasing this household "
            "is a single request: DELETE /api/profiles/{id}."
        ),
    }


def delete_profile(profile_id: str) -> dict[str, Any]:
    """Erase a household: facts, applications, reminders, consents, audit rows.

    One tombstone is written afterwards so the erasure itself stays auditable -
    the tombstone deliberately contains no personal data.
    """
    with connect() as conn:
        counts = {
            "profiles": conn.execute(
                "SELECT COUNT(*) AS c FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()["c"],
            "applications": conn.execute(
                "SELECT COUNT(*) AS c FROM applications WHERE profile_id = ?", (profile_id,)
            ).fetchone()["c"],
            "reminders": conn.execute(
                "SELECT COUNT(*) AS c FROM reminders WHERE profile_id = ?", (profile_id,)
            ).fetchone()["c"],
            "consents": conn.execute(
                "SELECT COUNT(*) AS c FROM consent WHERE profile_id = ?", (profile_id,)
            ).fetchone()["c"],
            "audit_rows": conn.execute(
                "SELECT COUNT(*) AS c FROM audit WHERE profile_id = ?", (profile_id,)
            ).fetchone()["c"],
        }
        for table, column in (
            ("profiles", "id"),
            ("applications", "profile_id"),
            ("reminders", "profile_id"),
            ("consent", "profile_id"),
            ("audit", "profile_id"),
        ):
            conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (profile_id,))
        _audit(
            conn,
            "profile_erased",
            profile_id,
            {
                "deleted": counts,
                "note": (
                    "Erasure honoured: facts, applications, reminders, consents and audit rows "
                    "removed. This tombstone proves the erasure and holds no personal data."
                ),
            },
        )
    return {"profile_id": profile_id, "deleted": counts, "erased_at": _now()}


def purge_expired(days: Optional[int] = None) -> dict[str, Any]:
    """Retention sweep: erase households older than the retention window."""
    window = _retention_days() if days is None else days
    cutoff = (datetime.now() - timedelta(days=window)).replace(microsecond=0).isoformat()
    with connect() as conn:
        rows = conn.execute("SELECT id FROM profiles WHERE created_at < ?", (cutoff,)).fetchall()
    erased = [row["id"] for row in rows]
    for pid in erased:
        delete_profile(pid)
    return {
        "retention_days": window,
        "cutoff": cutoff,
        "erased_profiles": erased,
        "count": len(erased),
        "note": "Deterministic sweep - run it on a timer in production.",
    }
