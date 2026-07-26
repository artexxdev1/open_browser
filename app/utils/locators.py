"""Locator resolution helpers."""

from __future__ import annotations

from playwright.async_api import Locator, Page


def resolve_locator(page: Page, locator: str | Locator) -> Locator:
    """Resolve a CSS selector string or return an existing Playwright locator.

    Args:
        page: Active Playwright page instance.
        locator: CSS selector or Playwright Locator.

    Returns:
        Resolved Playwright Locator.
    """
    if isinstance(locator, Locator):
        return locator
    return page.locator(locator)
