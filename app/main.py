"""Application orchestration and entry point."""

from __future__ import annotations

import asyncio
import logging

from playwright.async_api import Page

from app.browser.manager import BrowserManager
from app.config.settings import Settings, get_settings
from app.managers.session_manager import SessionManager
from app.services.chat_service import ChatService
from app.services.form_service import FormService
from app.services.login_service import LoginService
from app.services.navigation_service import NavigationService
from app.utils.logging import setup_logging
from app.utils.shutdown import ShutdownCoordinator

logger = logging.getLogger(__name__)


class AutomationApp:
    """High-level orchestrator for browser automation workflows."""

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
        self._shutdown = ShutdownCoordinator()

    async def run(self) -> None:
        """Execute the automation workflow with graceful shutdown support."""
        loop = asyncio.get_running_loop()
        self._shutdown.install_signal_handlers(loop)
        self._shutdown.register_cleanup(self._browser_manager.stop)

        storage_path = self._session_manager.get_storage_state_path()
        await self._browser_manager.start(storage_state=storage_path)

        try:
            await self._session_manager.ensure_authenticated(
                self._browser_manager.context,
                self._login_service,
            )

            page = await self._browser_manager.new_page()
            try:
                await self._run_automation(page)
            finally:
                await page.close()

            if not self._shutdown.is_shutting_down:
                await self._session_manager.save(self._browser_manager.context)
        finally:
            await self._browser_manager.stop()

    async def _run_automation(self, page: Page) -> None:
        """Open chat, send a message, and log the returned answer."""
        await self._chat_service.open_chat(page)
        answer = await self._chat_service.send_message(page)
        logger.info("Answer:\n%s", answer)
        logger.info("Automation completed for %s", self._settings.base_url)

    async def wait_for_shutdown(self) -> None:
        """Block until shutdown is requested."""
        await self._shutdown.wait_for_shutdown()


def validate_settings(settings: Settings) -> None:
    """Validate required configuration before starting automation."""
    missing: list[str] = []
    if not settings.base_url:
        missing.append("BASE_URL")

    if settings.uses_token_auth:
        if not settings.access_token:
            missing.append("ACCESS_TOKEN")
    else:
        if not settings.login_url:
            missing.append("LOGIN_URL")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


async def main() -> int:
    """Application entry point."""
    settings = get_settings()
    setup_logging(settings.log_dir, settings.log_level)

    try:
        validate_settings(settings)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    app = AutomationApp(settings)

    try:
        await app.run()
    except Exception:
        logger.exception("Automation failed")
        return 1

    logger.info("Automation service finished successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
