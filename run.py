"""Start SchemeSetu:  python run.py"""

from __future__ import annotations

import os
import uvicorn

from backend.app.config import settings


def main() -> None:
    # On Render, Fly.io, or cloud hosts, binding to 0.0.0.0 and reading $PORT is standard
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else settings.host)
    port = int(os.environ.get("PORT", settings.port))
    print(f"  {settings.app_name} -> http://{host}:{port}")
    print(f"  focus: {settings.state_focus} | llm: {'on' if settings.llm_config() else 'deterministic-only'}")
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=settings.app_env == "dev" and not os.environ.get("PORT"),
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
