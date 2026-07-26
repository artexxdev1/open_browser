"""Session persistence and validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.async_api import BrowserContext, Page

from app.config.settings import Settings
from app.models import SessionState

if TYPE_CHECKING:
    from app.services.login_service import LoginService

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage authenticated browser session storage state."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._state_path = settings.storage_state_path

    @property
    def state_path(self) -> Path:
        """Return the filesystem path for persisted session state."""
        return self._state_path

    def get_session_state(self) -> SessionState:
        """Return metadata about the persisted session file."""
        return SessionState(path=self._state_path, exists=self._state_path.is_file())

    def get_storage_state_path(self) -> str | None:
        """Return storage state path when a valid session file exists."""
        session = self.get_session_state()
        if not session.is_available:
            logger.info("No persisted session found at %s", self._state_path)
            return None

        if not self._is_valid_storage_file(self._state_path):
            logger.warning("Invalid session file at %s; ignoring", self._state_path)
            return None

        logger.info("Loaded session state from %s", self._state_path)
        return str(self._state_path)

    async def save(self, context: BrowserContext) -> None:
        """Persist cookies and local storage from the browser context."""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self._state_path))
        logger.info("Session saved to %s", self._state_path)

    async def is_session_expired(self, page: Page) -> bool:
        """Detect whether the current page indicates an expired session."""
        if self._settings.uses_token_auth:
            try:
                chat_input = page.locator(self._settings.chat_input_selector)
                if await chat_input.count() > 0 and await chat_input.first.is_visible():
                    return False
                logger.info("Chat input not visible; session appears expired")
                return True
            except Exception:
                logger.debug("Token session expiry check inconclusive", exc_info=True)
                return True

        expired_selector = self._settings.session_expired_selector
        if expired_selector:
            try:
                login_link = page.locator(expired_selector)
                if await login_link.count() > 0 and await login_link.first.is_visible():
                    logger.info("Session expired indicator detected: %s", expired_selector)
                    return True
            except Exception:
                logger.debug("Session expiry check inconclusive", exc_info=True)

        login_url = self._settings.login_url.lower()
        current_url = page.url.lower()
        if login_url and "login" in current_url and login_url in current_url:
            logger.info("Redirected to login page; session appears expired")
            return True

        return False

    async def ensure_authenticated(
        self,
        context: BrowserContext,
        login_service: LoginService,
    ) -> None:
        """Load or refresh the session, performing login when required."""
        storage_path = self.get_storage_state_path()
        page = await context.new_page()

        try:
            if storage_path:
                await page.goto(self._settings.base_url, wait_until="domcontentloaded")
                if not await self.is_session_expired(page):
                    logger.info("Existing session is valid")
                    return

                logger.info("Persisted session expired; re-authenticating")

            await login_service.login(context)
            await self.save(context)
        finally:
            await page.close()

    @staticmethod
    def _is_valid_storage_file(path: Path) -> bool:
        """Validate that the storage state file contains expected keys."""
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            return isinstance(data, dict) and "cookies" in data
        except (OSError, json.JSONDecodeError):
            return False
