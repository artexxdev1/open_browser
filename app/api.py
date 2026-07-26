"""FastAPI HTTP interface for GapGPT automation."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.automation import GapGPTAutomation
from app.config.settings import Settings, get_settings
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    """Incoming chat request body."""

    message: str = Field(..., min_length=1, max_length=100000)


class AskResponse(BaseModel):
    """Successful chat response body."""

    answer: str


class HealthResponse(BaseModel):
    """Service health payload."""

    status: str
    ready: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application with a warm browser session."""
    settings = settings or get_settings()
    setup_logging(settings.log_dir, settings.log_level)
    engine = GapGPTAutomation(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Start API immediately; warm browser in background so /health stays up.
        async def _warm() -> None:
            try:
                await engine.start()
            except Exception:
                logger.exception("Failed to warm GapGPT session on startup")

        import asyncio

        warm_task = asyncio.create_task(_warm())
        yield
        warm_task.cancel()
        await engine.stop()

    app = FastAPI(
        title="GapGPT API",
        version="1.0.0",
        lifespan=lifespan,
    )

    def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    @app.get("/", response_model=HealthResponse)
    async def root() -> HealthResponse:
        return HealthResponse(status="ok", ready=engine.ready)

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", ready=engine.ready)

    @app.post("/ask", response_model=AskResponse, dependencies=[Depends(require_api_key)])
    async def ask(body: AskRequest) -> AskResponse:
        try:
            answer = await engine.ask(body.message)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Ask failed")
            raise HTTPException(status_code=502, detail=f"GapGPT automation failed: {exc}") from exc
        return AskResponse(answer=answer)

    return app


app = create_app()
