"""Live smoke test for the LLM layer (Groq + OpenRouter).

Run:  python scripts/smoke_llm.py
It prints the provider chain, makes one JSON-mode call and one plain call, and
reports timings. Safe to run with no keys - it will say so and exit 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and crash on non-Latin output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app import llm  # noqa: E402


def main() -> int:
    health = llm.health()
    print("provider chain :", health["fallback_chain"])
    print("active         :", health["active"])
    print("speech-to-text :", health["speech_to_text"])
    if not health["available"]:
        print("No LLM key configured - deterministic mode is fine. Exiting 0.")
        return 0

    result = llm.chat(
        [{"role": "user", "content": "Reply in one short line: which state is Warangal in?"}],
        max_tokens=60,
    )
    if result is None:
        print("chat returned None")
        return 1
    print(f"plain call     : ok={result.ok} provider={result.provider} ms={result.ms}")
    print("text           :", (result.text or result.error)[:200])

    parsed, meta = llm.complete_json(
        'Return strict JSON: {"state": "...", "district": "..."} for this sentence: '
        "I live in Warangal, Telangana."
    )
    print("json call      :", parsed, "|", meta.provider if meta else None)
    print("stats          :", llm.stats())
    return 0 if (result.ok or (meta and meta.ok)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
