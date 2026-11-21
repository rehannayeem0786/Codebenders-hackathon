"""Central configuration, loaded from ``.env`` (python-dotenv).

Design rule for this hackathon build: **nothing is mandatory**. The product
must run with zero API keys, zero network, and zero installs beyond
fastapi/uvicorn. Keys only unlock the optional LLM layer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

# .env first, then .env.local so local overrides win. override=False keeps
# real shell env vars authoritative (useful in CI / judges' machines).
load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT / ".env.local", override=True)


def _s(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _b(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on", "y"}


def _i(name: str, default: int) -> int:
    try:
        return int(float((os.environ.get(name) or "").strip() or default))
    except (TypeError, ValueError):
        return default


def _f(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name) or "").strip() or default)
    except (TypeError, ValueError):
        return default


def _p(name: str, default: str) -> Path:
    """Resolve a possibly-relative path against the project root."""
    raw = Path(_s(name, default) or default)
    return raw if raw.is_absolute() else (ROOT / raw)


@dataclass(frozen=True)
class Settings:
    # app
    app_name: str
    app_env: str
    host: str
    port: int
    log_level: str
    state_focus: str
    default_language: str
    # data
    schemes_path: Path
    samples_path: Path
    db_path: Path
    data_stale_after_days: int
    # guardrails
    pii_redaction: bool
    block_sensitive_ids: bool
    # data rights (DPDP Act 2023): consent, retention, erasure
    consent_required: bool
    data_retention_days: int
    # graphify
    graphify_out: Path
    graphify_corpus: Path
    graphify_auto_import: bool
    # llm (Groq + OpenRouter only)
    llm_enabled: str
    llm_provider: str
    llm_temperature: float
    llm_timeout: float
    groq_api_key: str
    groq_base_url: str
    groq_model: str
    groq_stt_enabled: bool
    groq_stt_model: str
    groq_reasoning_effort: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    openrouter_referer: str
    openrouter_title: str

    # ---------------------------------------------------------------- helpers
    @property
    def root(self) -> Path:
        return ROOT

    def llm_config(self) -> dict[str, Any] | None:
        """Resolve the Groq/OpenRouter chat client from the environment.

        Only Groq and OpenRouter are supported. Both speak the OpenAI
        chat-completions protocol, so they share one HTTP path in
        :mod:`backend.app.llm`. Returns ``None`` when the LLM layer is off or
        no key is present - callers must always have a deterministic fallback.
        """
        if self.llm_enabled == "off":
            return None

        groq: dict[str, Any] = {}
        if self.groq_api_key:
            groq = {
                "provider": "groq",
                "api_key": self.groq_api_key,
                "base_url": self.groq_base_url.rstrip("/"),
                "model": self.groq_model,
                "style": "openai",
                "headers": {},
            }
        openrouter: dict[str, Any] = {}
        if self.openrouter_api_key:
            openrouter = {
                "provider": "openrouter",
                "api_key": self.openrouter_api_key,
                "base_url": self.openrouter_base_url.rstrip("/"),
                "model": self.openrouter_model,
                "style": "openai",
                # OpenRouter attribution (optional but recommended)
                "headers": {
                    "HTTP-Referer": self.openrouter_referer,
                    "X-Title": self.openrouter_title,
                },
            }

        if self.llm_provider == "groq":
            order = [groq]
        elif self.llm_provider == "openrouter":
            order = [openrouter]
        else:  # auto - Groq first (lower latency, generous free tier)
            order = [groq, openrouter]
        for cfg in order:
            if cfg:
                return cfg
        return None

    def stt_config(self) -> dict[str, Any] | None:
        """Speech-to-text config (Groq Whisper) or ``None``.

        This is how a person who types Telugu/Hindi poorly can simply speak:
        the browser records a short voice note, we transcribe it server-side
        with Whisper, then reuse the normal intake path.
        """
        if self.llm_enabled == "off" or not self.groq_stt_enabled or not self.groq_api_key:
            return None
        return {
            "provider": "groq",
            "api_key": self.groq_api_key,
            "base_url": self.groq_base_url.rstrip("/"),
            "model": self.groq_stt_model,
        }


def load_settings() -> Settings:
    return Settings(
        app_name=_s("APP_NAME", "SchemeSetu"),
        app_env=_s("APP_ENV", "dev"),
        host=_s("HOST", "127.0.0.1"),
        port=_i("PORT", 8000),
        log_level=_s("LOG_LEVEL", "INFO").upper(),
        state_focus=_s("STATE_FOCUS", "Telangana"),
        default_language=_s("DEFAULT_LANGUAGE", "en-IN"),
        schemes_path=_p("SCHEMES_PATH", "data/schemes.json"),
        samples_path=_p("SAMPLE_PROFILES_PATH", "data/sample_profiles.json"),
        db_path=_p("DB_PATH", "data/app.db"),
        data_stale_after_days=_i("DATA_STALE_AFTER_DAYS", 180),
        pii_redaction=_b("PII_REDACTION", True),
        block_sensitive_ids=_b("BLOCK_SENSITIVE_IDS", True),
        consent_required=_b("CONSENT_REQUIRED", False),
        data_retention_days=_i("DATA_RETENTION_DAYS", 90),
        graphify_out=_p("GRAPHIFY_OUT", "graphify-out/graph.json"),
        graphify_corpus=_p("GRAPHIFY_CORPUS", "corpus"),
        graphify_auto_import=_b("GRAPHIFY_AUTO_IMPORT", True),
        llm_enabled=_s("LLM_ENABLED", "auto").lower(),
        llm_provider=_s("LLM_PROVIDER", "auto").lower(),
        llm_temperature=_f("LLM_TEMPERATURE", 0.2),
        llm_timeout=_f("LLM_TIMEOUT_SECONDS", 45.0),
        groq_api_key=_s("GROQ_API_KEY"),
        groq_base_url=_s("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        groq_model=_s("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_stt_enabled=_b("GROQ_STT_ENABLED", True),
        groq_stt_model=_s("GROQ_STT_MODEL", "whisper-large-v3"),
        groq_reasoning_effort=_s("GROQ_REASONING_EFFORT", "low"),
        openrouter_api_key=_s("OPENROUTER_API_KEY"),
        openrouter_base_url=_s("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_model=_s("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"),
        openrouter_referer=_s("OPENROUTER_REFERER", "http://localhost:8000"),
        openrouter_title=_s("OPENROUTER_TITLE", "SchemeSetu"),
    )


settings = load_settings()

# Guardrail self-check: PS5 forbids collecting sensitive IDs.
if settings.block_sensitive_ids and not settings.pii_redaction:
    raise RuntimeError(
        "Invalid guardrail config: BLOCK_SENSITIVE_IDS=1 requires PII_REDACTION=1."
    )
