"""Start SchemeSetu:  python run.py"""

from __future__ import annotations

import uvicorn

from backend.app.config import settings


def main() -> None:
    print(f"  {settings.app_name} -> http://{settings.host}:{settings.port}")
    print(f"  focus: {settings.state_focus} | llm: {'on' if settings.llm_config() else 'deterministic-only'}")
    uvicorn.run(
        "backend.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "dev",
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
