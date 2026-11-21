"""PII / sensitive-ID guardrails.

SchemeSetu must not become one more place where an Aadhaar number leaks.
Every free-text string that enters the system - typed notes, voice
transcripts, LLM prompts *and* LLM replies - passes through :func:`redact`
first. The redactions are then reported back to the citizen, so the
guardrail is a visible feature instead of a hidden promise.

Two levels, mirroring the env switches:

* ``PII_REDACTION=1`` (default) - :func:`redact` masks Aadhaar/PAN/mobile/
  bank-account/OTP/email/IFSC, keeping only the last 4 characters so the
  citizen can still recognise their own document.
* ``BLOCK_SENSITIVE_IDS=1`` (default) - sensitive *keys* in an incoming
  payload (``aadhaar``, ``pan``, ``bank_account_number`` ...) are dropped
  outright, and :func:`strict_check` can refuse a payload.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .config import settings
from .models import FORBIDDEN_FIELDS, PROFILE_FIELDS

# Field names that are safe to persist on a profile ("name" is display-only).
ALLOWED_PROFILE_KEYS = {"name", "notes", *PROFILE_FIELDS.keys()}


class SensitiveDataError(ValueError):
    """Raised when a payload carries a sensitive ID we refuse to accept."""


@dataclass(frozen=True)
class Finding:
    """One sensitive token found in a piece of text."""

    kind: str
    label: str
    start: int
    end: int
    masked: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "masked": self.masked,
            "start": self.start,
            "end": self.end,
        }


# Ordered most-specific first: we mask greedily, so later patterns must never
# be able to re-match a span that an earlier pattern already claimed.
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("otp", "OTP / PIN",
     re.compile(r"(?i)\b(?:otp|one[\s-]?time\s+password|upi\s+pin|atm\s+pin)\b[^\d]{0,12}(\d{4,8})")),
    ("email", "email address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")),
    ("phone", "mobile number", re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{9}\b")),
    ("pan", "PAN", re.compile(r"\b[A-Z]{5}\s?\d{4}\s?[A-Z]\b")),
    ("ifsc", "IFSC code", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("aadhaar", "Aadhaar number", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("bank_account", "bank account number", re.compile(r"\b\d{9,18}\b")),
]

_STATS: dict[str, Any] = {"redactions": 0, "by_kind": {}, "dropped_keys": 0}


# --------------------------------------------------------------------------- #
# core
# --------------------------------------------------------------------------- #
def _mask_token(raw: str, keep_last: int = 4) -> str:
    """``1234 5678 9012`` -> ``XXXX XXXX 9012`` (separators preserved)."""
    alnum = [i for i, ch in enumerate(raw) if ch.isalnum()]
    if len(alnum) <= keep_last:
        return "X" * len(raw)
    first_kept = alnum[len(alnum) - keep_last]
    out = []
    for i, ch in enumerate(raw):
        if not ch.isalnum():
            out.append(ch)
        elif i >= first_kept:
            out.append(ch.upper())
        else:
            out.append("X")
    return "".join(out)


def find(text: str) -> list[Finding]:
    """Return the sensitive tokens in ``text`` (non-overlapping)."""
    if not text:
        return []
    taken: list[tuple[int, int]] = []
    found: list[Finding] = []
    for kind, label, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            span = m.span(1) if kind == "otp" else m.span()
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue
            taken.append(span)
            found.append(
                Finding(
                    kind=kind,
                    label=label,
                    start=span[0],
                    end=span[1],
                    masked=_mask_token(m.group(1) if kind == "otp" else m.group(0)),
                )
            )
    found.sort(key=lambda f: f.start)
    return found


def redact(text: str) -> tuple[str, list[Finding]]:
    """Return ``(safe_text, findings)``. No-op when redaction is switched off."""
    if not text or not settings.pii_redaction:
        return text, []
    findings = find(text)
    if not findings:
        return text, []
    out: list[str] = []
    cursor = 0
    for f in findings:
        out.append(text[cursor:f.start])
        out.append(f.masked)
        cursor = f.end
    out.append(text[cursor:])
    _bump(findings)
    return "".join(out), findings


def redact_text(text: str) -> str:
    """Convenience wrapper used at every LLM boundary."""
    return redact(text)[0]


def redact_deep(value: Any) -> Any:
    """Recursively redact strings inside dicts / lists (for JSON payloads)."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {k: redact_deep(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_deep(v) for v in value]
    return value


def sanitize_profile(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Strip forbidden keys and redact free text before anything is stored.

    Returns ``(clean_profile, report)`` where the report is written to be
    shown to the citizen: which keys we dropped and which tokens we masked.
    """
    clean: dict[str, Any] = {}
    dropped: list[str] = []
    findings: list[Finding] = []
    for key, value in (data or {}).items():
        if key in FORBIDDEN_FIELDS:
            dropped.append(key)
            if settings.pii_redaction:
                _STATS["dropped_keys"] += 1
            continue
        if key not in ALLOWED_PROFILE_KEYS:
            dropped.append(key)
            continue
        if isinstance(value, str):
            safe, tokens = redact(value)
            findings.extend(tokens)
            clean[key] = safe
        else:
            clean[key] = value
    report: dict[str, Any] = {
        "dropped_keys": sorted(set(dropped)),
        "redactions": [f.as_dict() for f in findings],
        "kept_field_count": len(clean),
    }
    if dropped:
        report["message"] = (
            "For your safety we do not collect or store: "
            + ", ".join(report["dropped_keys"])
            + ". Please share only the last 4 digits of any ID."
        )
    return clean, report


def strict_check(text: str) -> None:
    """Refuse *raw* sensitive IDs when ``BLOCK_SENSITIVE_IDS=1``."""
    if not settings.block_sensitive_ids:
        return
    blocked = [
        f
        for f in find(text)
        if f.kind in {"aadhaar", "pan", "bank_account", "ifsc", "otp"}
    ]
    if blocked:
        labels = ", ".join(sorted({f.label for f in blocked}))
        raise SensitiveDataError(
            f"Blocked {labels}. SchemeSetu never needs your full ID number - "
            "remove it and try again, or share only the last 4 digits."
        )


def summarise(findings: Iterable[Finding] | Iterable[dict[str, Any]]) -> str:
    """One friendly sentence for the UI banner."""
    labels: set[str] = set()
    for f in findings:
        labels.add(f["label"] if isinstance(f, dict) else f.label)
    if not labels:
        return ""
    return "Privacy shield: removed " + ", ".join(sorted(labels)) + " before saving."


def stats() -> dict[str, Any]:
    return {
        "redactions": _STATS["redactions"],
        "by_kind": dict(_STATS["by_kind"]),
        "dropped_keys": _STATS["dropped_keys"],
    }


def reset_stats() -> None:
    _STATS.update({"redactions": 0, "by_kind": {}, "dropped_keys": 0})


def guardrail_report() -> dict[str, Any]:
    """Everything the UI needs to prove the guardrails are live."""
    return {
        "pii_redaction": settings.pii_redaction,
        "block_sensitive_ids": settings.block_sensitive_ids,
        "forbidden_fields": sorted(FORBIDDEN_FIELDS),
        "patterns_active": [{"kind": k, "label": l} for k, l, _ in _PATTERNS],
        "session_stats": stats(),
        "policy": (
            "We never ask for or store Aadhaar, PAN, full bank account numbers or OTPs. "
            "Free text is masked before it is saved or sent to any model."
        ),
    }


def _bump(findings: list[Finding]) -> None:
    _STATS["redactions"] += len(findings)
    for f in findings:
        _STATS["by_kind"][f.kind] = _STATS["by_kind"].get(f.kind, 0) + 1
