"""Browser lifecycle management."""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.config.settings import Settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Launch and manage Playwright browser instances for automation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    @property
    def context(self) -> BrowserContext:
        """Return the active browser context."""
        if self._context is None:
            raise RuntimeError("Browser context is not initialized")
        return self._context

    @property
    def is_running(self) -> bool:
        """Return True when the browser is active."""
        return self._browser is not None and self._browser.is_connected()

    async def start(self, storage_state: str | None = None) -> BrowserContext:
        """Launch browser and create a browser context."""
        if self.is_running:
            return self.context

        browser_name = self._settings.browser_name
        logger.info("Starting %s (headless=%s)", browser_name, self._settings.headless)
        self._playwright = await async_playwright().start()
        launcher = getattr(self._playwright, browser_name)

        launch_kwargs: dict[str, Any] = {"headless": self._settings.headless}
        if browser_name == "chromium":
            launch_kwargs["args"] = self._settings.browser_args

        self._browser = await launcher.launch(**launch_kwargs)

        context_options: dict[str, Any] = {
            "viewport": {"width": 1024, "height": 720},
            "ignore_https_errors": True,
        }
        if storage_state:
            context_options["storage_state"] = storage_state

        self._context = await self._browser.new_context(**context_options)
        self._context.set_default_timeout(self._settings.timeout)
        self._context.set_default_navigation_timeout(self._settings.navigation_timeout)

        logger.info("Browser context created")
        return self._context

    async def new_page(self) -> Page:
        """Open a new page in the active browser context."""
        return await self.context.new_page()

    async def stop(self) -> None:
        """Close browser resources in reverse initialization order."""
        logger.info("Stopping browser resources")

        if self._context is not None:
            await self._context.close()
            self._context = None

        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Browser stopped")
