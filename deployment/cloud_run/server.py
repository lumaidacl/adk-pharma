"""FastAPI entrypoint exposing the ADK agents directory for Google Cloud Run."""

import os
from pathlib import Path

from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
AGENTS_DIR: str = os.getenv("AGENTS_DIR", str(PROJECT_ROOT / "agents"))

SERVE_WEB_UI: bool = os.getenv("SERVE_WEB_UI", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}
ALLOWED_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("ALLOW_ORIGINS", "*").split(",")
    if origin.strip()
]

app: FastAPI = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=SERVE_WEB_UI,
    allow_origins=ALLOWED_ORIGINS,
)


@app.get("/healthz", tags=["health"])
async def health_check() -> dict[str, str]:
    """Liveness and readiness probe endpoint for Cloud Run."""
    return {"status": "ok", "service": "pharma-rd-radar"}


if __name__ == "__main__":
    import uvicorn

    port: int = int(os.getenv("PORT", "8080"))
    uvicorn.run("deployment.cloud_run.server:app", host="0.0.0.0", port=port)

