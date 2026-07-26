"""Application entry point — runs the GapGPT API server."""

from __future__ import annotations

import logging

import uvicorn

from app.config.settings import get_settings
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def validate_settings() -> None:
    """Validate required configuration before starting the API."""
    settings = get_settings()
    missing: list[str] = []
    if not settings.base_url:
        missing.append("BASE_URL")
    if settings.uses_token_auth and not settings.access_token:
        missing.append("ACCESS_TOKEN")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def main() -> None:
    """Start uvicorn with the FastAPI app."""
    settings = get_settings()
    setup_logging(settings.log_dir, settings.log_level)
    validate_settings()

    logger.info("Starting GapGPT API on %s:%s", settings.host, settings.port)
    uvicorn.run(
        "app.api:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
