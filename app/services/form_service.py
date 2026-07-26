"""Form interaction service."""

from __future__ import annotations

import logging

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.config.settings import Settings
from app.exceptions import ElementNotFoundError, TimeoutError
from app.utils.locators import resolve_locator

logger = logging.getLogger(__name__)


class FormService:
    """Helper methods for interacting with form elements."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fill_input(
        self,
        page: Page,
        locator: str | Locator,
        text: str,
        *,
        clear_first: bool = True,
    ) -> None:
        """Fill a text input identified by selector or locator."""
        element = resolve_locator(page, locator)
        await self._ensure_visible(element, locator)

        if clear_first:
            await element.fill("")

        await element.fill(text)
        logger.debug("Filled input: %s", locator)

    async def click(self, page: Page, locator: str | Locator) -> None:
        """Click an element identified by selector or locator."""
        element = resolve_locator(page, locator)
        await self._ensure_visible(element, locator)
        await element.click()
        logger.debug("Clicked element: %s", locator)

    async def press(self, page: Page, key: str) -> None:
        """Press a keyboard key on the active page."""
        await page.keyboard.press(key)
        logger.debug("Pressed key: %s", key)

    async def paste(self, page: Page, text: str) -> None:
        """Insert text via clipboard paste semantics."""
        await page.evaluate(
            """async (value) => {
                await navigator.clipboard.writeText(value);
            }""",
            text,
        )
        await page.keyboard.press("Control+V")
        logger.debug("Pasted text (%d chars)", len(text))

    async def clear(self, page: Page, locator: str | Locator) -> None:
        """Clear the contents of an input element."""
        element = resolve_locator(page, locator)
        await self._ensure_visible(element, locator)
        await element.fill("")
        logger.debug("Cleared input: %s", locator)

    async def _ensure_visible(self, element: Locator, locator: str | Locator) -> None:
        """Verify an element exists and is visible before interaction."""
        try:
            await element.wait_for(state="visible", timeout=self._settings.timeout)
        except PlaywrightTimeoutError as exc:
            raise ElementNotFoundError(
                "Element not found or not visible",
                context={"locator": str(locator)},
            ) from exc
