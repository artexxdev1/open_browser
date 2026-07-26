"""Chat interaction service for GapGPT-style interfaces."""

from __future__ import annotations

import logging

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.config.settings import Settings
from app.exceptions import TimeoutError
from app.services.form_service import FormService
from app.services.navigation_service import NavigationService

logger = logging.getLogger(__name__)


class ChatService:
    """Send messages through the chat UI and collect the reply."""

    def __init__(
        self,
        settings: Settings,
        navigation_service: NavigationService,
        form_service: FormService,
    ) -> None:
        self._settings = settings
        self._navigation = navigation_service
        self._form = form_service

    async def open_chat(self, page: Page) -> None:
        """Navigate to the chat page and wait for the input to be ready."""
        await self._navigation.navigate_safely(
            page,
            self._settings.base_url,
            ready_selector=self._settings.chat_input_selector,
            wait_until="domcontentloaded",
        )
        logger.info("Chat page ready")

    async def send_message(self, page: Page, message: str | None = None) -> str:
        """Type a message, submit it, wait for the reply, and return the text."""
        text = message or self._settings.test_message
        input_selector = self._settings.chat_input_selector
        submit_selector = self._settings.chat_submit_selector
        answer_selector = self._settings.chat_answer_selector

        before_count = await page.locator(answer_selector).count()

        await self._form.click(page, input_selector)
        await self._form.fill_input(page, input_selector, text)
        await self._form.click(page, submit_selector)
        logger.info("Message submitted (%d chars)", len(text))

        answer = await self.wait_for_answer(page, previous_count=before_count)
        return answer

    async def wait_for_answer(self, page: Page, *, previous_count: int = 0) -> str:
        """Wait until a new answer appears in the answer container and return it."""
        answer_selector = self._settings.chat_answer_selector
        timeout = self._settings.answer_timeout
        answers = page.locator(answer_selector)

        try:
            await page.wait_for_function(
                """([selector, previous]) => {
                    const nodes = document.querySelectorAll(selector);
                    return nodes.length > previous;
                }""",
                arg=[answer_selector, previous_count],
                timeout=timeout,
            )
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                "Timed out waiting for chat answer",
                context={
                    "selector": answer_selector,
                    "timeout_ms": timeout,
                    "previous_count": previous_count,
                },
            ) from exc

        # Prefer the newest answer bubble once streaming settles.
        latest = answers.last
        await latest.wait_for(state="visible", timeout=timeout)

        # Wait briefly for streaming text to stabilize (same text twice in a row).
        previous_text = ""
        stable_reads = 0
        for _ in range(60):
            current_text = (await latest.inner_text()).strip()
            if current_text and current_text == previous_text:
                stable_reads += 1
                if stable_reads >= 2:
                    break
            else:
                stable_reads = 0
                previous_text = current_text
            await page.wait_for_timeout(500)

        answer_text = (await latest.inner_text()).strip()
        logger.info("Answer received (%d chars)", len(answer_text))
        return answer_text
