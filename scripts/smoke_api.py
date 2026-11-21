"""End-to-end API smoke test through FastAPI's TestClient.

Run:  python scripts/smoke_api.py
Exercises every route a judge will touch, including one Rule Studio edit.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and crash on Telugu/Hindi output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

client = TestClient(app)


def check(label: str, condition: bool, extra: str = "") -> None:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{(' - ' + extra) if extra else ''}")
    if not condition:
        raise SystemExit(1)


def main() -> int:
    health = client.get("/api/health").json()
    check("health", health["app"] == "SchemeSetu", f"{health['graph']['schemes']} schemes, llm={health['llm']['active']}")
    check("guardrails active", health["guardrails"]["pii_redaction"] and health["guardrails"]["block_sensitive_ids"])

    i18n = client.get("/api/i18n/te").json()
    check("telugu strings", bool(i18n["ui"]["nav.results"]), i18n["ui"]["nav.results"])

    samples = client.get("/api/samples").json()["samples"]
    check("samples loaded", len(samples) >= 3, f"{len(samples)} samples")

    intake = client.post(
        "/api/intake",
        json={
            "text": (
                "I am 58, a widow in Warangal. White ration card, 2 acres of land, "
                "a bank account. My aadhaar is 1234 5678 9012."
            ),
            "language": "en",
            "save": True,
            "plan_reminders": True,
            "use_llm": False,
        },
    ).json()
    check("intake redacted aadhaar", "XXXX" in (intake["intake"]["transcript"] or ""), intake["intake"]["privacy_note"])
    check("profile saved", bool(intake["profile_id"]), intake["profile_id"])
    check("matches returned", len(intake["matches"]) > 5, intake["summary"]["headline"])
    check("why[] present", all(m["why"] for m in intake["matches"]))
    check("questions ranked", len(intake["next_questions"]) > 0, intake["next_questions"][0]["field"])
    pid = intake["profile_id"]

    verdicts = {m["scheme_id"]: m["verdict"] for m in intake["matches"]}
    aasara = next(m for m in intake["matches"] if m["scheme_id"] == "ts-aasara-oldage")
    check(
        "widow reaches Aasara old-age (pension question flagged)",
        aasara["verdict"] in {"likely_eligible", "possible", "needs_info"}
        and any("pension" in q["field"] for q in aasara["unlock_questions"]),
        f"verdict={aasara['verdict']}, unknown={[q['field'] for q in aasara['unlock_questions']]}",
    )
    check(
        "BPL widow gets health cover",
        verdicts.get("pmjay") == "likely_eligible" and verdicts.get("arogyasri-te") == "likely_eligible",
        f"pmjay={verdicts.get('pmjay')}, aarogyasri={verdicts.get('arogyasri-te')}",
    )

    graph = client.get("/api/graph", params={"profile_id": pid}).json()
    check("reasoning graph", graph["node_count"] > 20 and graph["edge_count"] > 20, f"{graph['node_count']} nodes")
    check("reasoning paths", len(graph["paths"]) > 20, f"{len(graph['paths'])} fact->rule->scheme rows")

    search = client.get("/api/graph/search", params={"q": "aasara"}).json()["results"]
    check("graph search", len(search) > 0, search[0]["id"])

    detail = client.get("/api/schemes/ts-aasara-oldage").json()
    check("scheme detail", detail["rule_count"] > 3 and detail["source_name"], f"{detail['rule_count']} rules")

    apps = client.post(
        "/api/applications",
        json={"profile_id": pid, "scheme_id": "ts-aasara-oldage", "scheme_name": "Aasara", "status": "documents_pending"},
    ).json()
    check("application created", apps["id"] > 0, str(apps["id"]))
    listed = client.get("/api/applications", params={"profile_id": pid}).json()["applications"]
    check("application listed", len(listed) == 1)

    student = next(s for s in samples if s["id"] == "student-hyderabad")
    scholar = client.post(
        "/api/intake",
        json={
            "text": student["text"],
            "form": student["form"],
            "language": "en",
            "save": True,
            "plan_reminders": True,
            "use_llm": False,
        },
    ).json()
    scholar_verdicts = {m["scheme_id"]: m["verdict"] for m in scholar["matches"]}
    check(
        "student matched to a scholarship",
        scholar_verdicts.get("nsp-pre-matric-sc") == "likely_eligible",
        f"verdict={scholar_verdicts.get('nsp-pre-matric-sc')}",
    )
    reminders = {"reminders": scholar["reminders_created"]}
    check("reminders planned", bool(reminders["reminders"]), f"{len(reminders['reminders'])} queued")
    due = client.get("/api/reminders/due", params={"window_days": 90}).json()["due"]
    check("due reminders", len(due) >= 1, due[0]["message"][:60] if due else "")

    studio = client.get("/api/rule-studio").json()
    check("rule studio payload", len(studio["schemes"]) >= 10, f"{len(studio['schemes'])} schemes")

    sim = client.post(
        "/api/rule-studio/simulate",
        json={
            "scheme_id": "ts-aasara-oldage",
            "profile_id": pid,
            "language": "en",
            "overrides": {"aasara.age": {"value": 60, "op": "gte"}},
        },
    ).json()
    check("simulate returns diff", "aasara.age" in sim["diff"])
    check("verdict moved", sim["before"]["verdict"] != sim["after"]["verdict"], f"{sim['before']['verdict']} -> {sim['after']['verdict']}")

    narrate = client.get("/api/narrate/pmjay", params={"lang": "te", "profile_id": pid}).json()
    check("narrate call", narrate["verdict"] in {"likely_eligible", "possible", "needs_info", "not_eligible"}, narrate["method"])

    fields = client.get("/api/fields", params={"lang": "hi"}).json()
    check("field vocabulary", fields["count"] > 30, f"{fields['count']} facts")

    print("\nALL API CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
