"""Smoke test for the intake pipeline (rules + optional LLM).

Run:  python scripts/smoke_intake.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and crash on Telugu/Hindi output.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app import intake  # noqa: E402

SAMPLES = [
    "I am 58 years old, a widow in Warangal. We have a white ration card and 2 acres of land. "
    "My son studies in class 9. My aadhaar is 1234 5678 9012 if you need it.",
    "నేను 45 ఏళ్ల రైతు, ఖమ్మం జిల్లా. మాకు 3 ఎకరాల భూమి ఉంది, రేషన్ కార్డు ఉంది. "
    "ఆదాయం సంవత్సరానికి 80000. బ్యాంకు ఖాతా ఉంది.",
    "मैं 30 साल की महिला हूँ, हैदराबाद से। मेरी बेटी कक्षा 10 में पढ़ती है, हमारे पास राशन कार्ड है। "
    "सरकारी नौकरी नहीं है।",
]


def main() -> int:
    for i, text in enumerate(SAMPLES, 1):
        result = intake.interpret(text, use_llm=True, language="te" if i == 2 else "hi" if i == 3 else "en")
        print(f"--- sample {i} ({result['method']}) ---")
        print("facts  :", json.dumps(result["facts"], ensure_ascii=False, default=str))
        print("source :", result["field_sources"])
        print("privacy:", result["privacy_note"] or "(nothing to redact)")
        if result.get("llm"):
            print("llm    :", result["llm"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
