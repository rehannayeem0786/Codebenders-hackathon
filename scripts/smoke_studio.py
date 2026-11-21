"""Rule Studio apply/restore test.

Proves that an edit really is written to ``data/schemes.json`` (with a ``.bak``
and an INFERRED provenance re-tag), then restores the file so the curated data
stays exactly as it was.

Run:  python scripts/smoke_studio.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import graph_store  # noqa: E402
from backend.app.config import settings  # noqa: E402
from backend.app.main import app  # noqa: E402

client = TestClient(app)
SCHEME_ID = "ts-aasara-disability"


def read_scheme() -> dict:
    raw = json.loads(settings.schemes_path.read_text(encoding="utf-8"))
    return next(s for s in raw["schemes"] if s["id"] == SCHEME_ID)


def main() -> int:
    before = read_scheme()
    print(f"before : provenance={before['provenance']} rules={len(before['rules'])}")

    from backend.app.main import ADMIN_TOKEN  # noqa: E402

    response = client.post(
        "/api/rule-studio/apply",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "scheme_id": SCHEME_ID,
            "language": "en",
            "persist": True,
            "overrides": {"disability.percent": {"value": 60, "source_note": "edited during the demo"}},
        },
    )
    if response.status_code != 200:
        print("FAIL:", response.status_code, response.text[:400])
        return 1
    payload = response.json()

    after = read_scheme()
    rule = next(r for r in after["rules"] if r["id"] == "disability.percent")
    print(f"applied: {payload['applied']}")
    print(f"backup : {payload['backup']}")
    print(f"after  : provenance={after['provenance']} edited_on={after.get('edited_on')} value={rule['value']}")
    assert after["provenance"] == "INFERRED", "provenance should be re-tagged INFERRED after a human edit"
    assert rule["value"] == 60

    # restore the curated file so the repository data is unchanged
    backup = settings.schemes_path.with_suffix(".json.bak")
    original = json.loads(backup.read_text(encoding="utf-8"))
    settings.schemes_path.write_text(json.dumps(original, ensure_ascii=False, indent=2), encoding="utf-8")
    graph_store.invalidate()
    restored = read_scheme()
    print(f"restored: provenance={restored['provenance']} value={next(r for r in restored['rules'] if r['id'] == 'disability.percent')['value']}")
    assert restored["provenance"] == before["provenance"]

    print("OK - apply persists, provenance is honest, and the .bak restores cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
