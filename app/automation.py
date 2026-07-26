"""Reusable GapGPT automation engine used by the API server."""

from __future__ import annotations

import asyncio
import logging

from app.browser.manager import BrowserManager
from app.config.settings import Settings
from app.managers.session_manager import SessionManager
from app.services.chat_service import ChatService
from app.services.form_service import FormService
from app.services.login_service import LoginService
from app.services.navigation_service import NavigationService

logger = logging.getLogger(__name__)


class GapGPTAutomation:
    """Launch browser per request to avoid OOM on small VPS hosts."""

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

    @property
    def ready(self) -> bool:
        """API is ready even when browser is cold (launched on demand)."""
        return True

    async def start(self) -> None:
        """Optional warm path — disabled by default on low-memory servers."""
        if not self._settings.warm_on_start:
            logger.info("Warm-on-start disabled; browser will launch per request")
            return
        await self._open_session()
        await self._browser_manager.stop()

    async def stop(self) -> None:
        """Ensure browser is closed."""
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
                    await self._open_session()
                    page = await self._browser_manager.new_page()
                    await self._chat_service.open_chat(page)
                    answer = await self._chat_service.send_message(page, text)
                    return answer
                except Exception as exc:
                    last_error = exc
                    logger.exception("ask() attempt %s failed", attempt)
                    if attempt < 3:
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    raise
                finally:
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
                    await self._browser_manager.stop()

        assert last_error is not None
        raise last_error

    async def _open_session(self) -> None:
        if self._browser_manager.is_running:
            await self._browser_manager.stop()
        await self._browser_manager.start(storage_state=None)
        await self._login_service.login(self._browser_manager.context)
        await self._session_manager.save(self._browser_manager.context)
