"""Reusable GapGPT automation engine used by the API server."""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import Page

from app.browser.manager import BrowserManager
from app.config.settings import Settings
from app.managers.session_manager import SessionManager
from app.services.chat_service import ChatService
from app.services.form_service import FormService
from app.services.login_service import LoginService
from app.services.navigation_service import NavigationService

logger = logging.getLogger(__name__)


class GapGPTAutomation:
    """Keep a browser session warm and process chat requests serially."""

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
        self._page: Page | None = None
        self._ready = False

    @property
    def ready(self) -> bool:
        """Return True when the browser session is initialized."""
        return self._ready

    async def start(self) -> None:
        """Launch browser, authenticate with cookie, and open chat."""
        if self._ready:
            return

        await self._browser_manager.start(storage_state=None)
        await self._login_service.login(self._browser_manager.context)
        await self._session_manager.save(self._browser_manager.context)

        self._page = await self._browser_manager.new_page()
        await self._chat_service.open_chat(self._page)
        self._ready = True
        logger.info("GapGPT automation ready")

    async def stop(self) -> None:
        """Close page and browser resources."""
        self._ready = False
        if self._page is not None:
            try:
                await self._page.close()
            except Exception:
                logger.debug("Page close failed", exc_info=True)
            self._page = None
        await self._browser_manager.stop()

    async def ask(self, message: str) -> str:
        """Send a message to GapGPT and return the completed answer."""
        if not message or not message.strip():
            raise ValueError("message must not be empty")

        async with self._lock:
            if not self._ready or self._page is None:
                await self.start()

            assert self._page is not None
            try:
                # Ensure chat input is still available; re-auth if needed.
                input_box = self._page.locator(self._settings.chat_input_selector)
                if await input_box.count() == 0 or not await input_box.first.is_visible():
                    logger.warning("Chat input missing; re-authenticating")
                    await self._page.close()
                    await self._login_service.login(self._browser_manager.context)
                    self._page = await self._browser_manager.new_page()
                    await self._chat_service.open_chat(self._page)

                return await self._chat_service.send_message(self._page, message.strip())
            except Exception:
                logger.exception("ask() failed; resetting session")
                self._ready = False
                try:
                    if self._page is not None:
                        await self._page.close()
                except Exception:
                    pass
                self._page = None
                await self._browser_manager.stop()
                raise
