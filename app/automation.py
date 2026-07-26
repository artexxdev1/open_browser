"""Reusable GapGPT automation engine used by the API server."""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import Error as PlaywrightError

from app.browser.manager import BrowserManager
from app.config.settings import Settings
from app.managers.session_manager import SessionManager
from app.services.chat_service import ChatService
from app.services.form_service import FormService
from app.services.login_service import LoginService
from app.services.navigation_service import NavigationService

logger = logging.getLogger(__name__)


class GapGPTAutomation:
    """Authenticate once, then handle each ask on a fresh page."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._browser_manager = BrowserManager(settings)
        self._session_manager = SessionManager(settings)
        self._navigation_service = NavigationService(settings)
        self._form_service = FormService(settings)
        self._login_service = LoginService(
            settings,
            self._navigation_service,
            self._form_service,
        )
        self._chat_service = ChatService(
            settings,
            self._navigation_service,
            self._form_service,
        )
        self._lock = asyncio.Lock()
        self._ready = False

    @property
    def ready(self) -> bool:
        """Return True when the browser context is authenticated."""
        return self._ready and self._browser_manager.is_running

    async def start(self) -> None:
        """Launch browser and authenticate with the accessToken cookie."""
        if self.ready:
            return

        if self._browser_manager.is_running:
            await self._browser_manager.stop()

        await self._browser_manager.start(storage_state=None)
        await self._login_service.login(self._browser_manager.context)
        await self._session_manager.save(self._browser_manager.context)
        self._ready = True
        logger.info("GapGPT automation ready")

    async def stop(self) -> None:
        """Close browser resources."""
        self._ready = False
        await self._browser_manager.stop()

    async def ask(self, message: str) -> str:
        """Send a message to GapGPT and return the completed answer."""
        if not message or not message.strip():
            raise ValueError("message must not be empty")

        text = message.strip()
        last_error: Exception | None = None

        async with self._lock:
            for attempt in range(1, 4):
                page = None
                try:
                    if not self.ready:
                        await self.start()

                    page = await self._browser_manager.new_page()
                    await self._chat_service.open_chat(page)
                    return await self._chat_service.send_message(page, text)
                except Exception as exc:
                    last_error = exc
                    logger.exception("ask() attempt %s failed", attempt)
                    self._ready = False
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    try:
                        await self._browser_manager.stop()
                    except Exception:
                        logger.debug("browser stop after crash failed", exc_info=True)
                    if attempt < 3 and self._is_recoverable(exc):
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    raise
                finally:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass

        assert last_error is not None
        raise last_error

    @staticmethod
    def _is_recoverable(exc: Exception) -> bool:
        message = str(exc).lower()
        return isinstance(exc, PlaywrightError) or "crash" in message or "target closed" in message
