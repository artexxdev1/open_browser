"""Page navigation service."""

from __future__ import annotations

import logging
from typing import Literal

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.config.settings import Settings
from app.exceptions import NavigationError, TimeoutError
from app.utils.retry import with_retries

logger = logging.getLogger(__name__)

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]
SelectorState = Literal["attached", "detached", "hidden", "visible"]


class NavigationService:
    """Reusable, wait-based navigation helpers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._retry = with_retries(settings)

    async def open_page(
        self,
        page: Page,
        url: str,
        *,
        wait_until: WaitUntil = "domcontentloaded",
    ) -> None:
        """Navigate to a URL and wait for the requested load state.

        Args:
            page: Active Playwright page.
            url: Destination URL.
            wait_until: Playwright load state to wait for.

        Raises:
            NavigationError: When navigation fails after retries.
        """
        try:
            await self._retry(self._goto)(page, url, wait_until)
            logger.info("Opened page: %s", url)
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                "Navigation timed out",
                context={"url": url, "wait_until": wait_until},
            ) from exc
        except Exception as exc:
            raise NavigationError(
                "Failed to open page",
                context={"url": url, "error": str(exc)},
            ) from exc

    async def wait_for_load(
        self,
        page: Page,
        *,
        wait_until: WaitUntil = "domcontentloaded",
    ) -> None:
        """Wait for the current page to reach a load state."""
        try:
            await page.wait_for_load_state(wait_until)
            logger.debug("Page reached load state: %s", wait_until)
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                "Page load timed out",
                context={"url": page.url, "wait_until": wait_until},
            ) from exc

    async def wait_for_selector(
        self,
        page: Page,
        selector: str,
        *,
        state: SelectorState = "visible",
        timeout: int | None = None,
    ) -> None:
        """Wait until a selector matches the requested state.

        Args:
            page: Active Playwright page.
            selector: CSS selector to wait for.
            state: Desired element state.
            timeout: Optional override for the default timeout.

        Raises:
            TimeoutError: When the selector does not appear in time.
        """
        try:
            await page.wait_for_selector(
                selector,
                state=state,
                timeout=timeout or self._settings.timeout,
            )
            logger.debug("Selector ready (%s): %s", state, selector)
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                "Selector wait timed out",
                context={"selector": selector, "state": state, "url": page.url},
            ) from exc

    async def navigate_safely(
        self,
        page: Page,
        url: str,
        *,
        ready_selector: str | None = None,
        wait_until: WaitUntil = "domcontentloaded",
    ) -> None:
        """Navigate to a page and optionally wait for a readiness selector."""
        await self.open_page(page, url, wait_until=wait_until)
        await self.wait_for_load(page, wait_until=wait_until)

        if ready_selector:
            await self.wait_for_selector(
                page,
                ready_selector,
                timeout=self._settings.navigation_timeout,
            )

    @staticmethod
    async def _goto(page: Page, url: str, wait_until: WaitUntil) -> None:
        """Internal navigation helper used by retry logic."""
        await page.goto(url, wait_until=wait_until)
