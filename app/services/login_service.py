"""Login workflow service."""

from __future__ import annotations

import logging

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from app.config.settings import Settings
from app.exceptions import ElementNotFoundError, LoginError, TimeoutError
from app.services.form_service import FormService
from app.services.navigation_service import NavigationService
from app.utils.retry import with_retries

logger = logging.getLogger(__name__)


class LoginService:
    """Authenticate against the configured target website."""

    def __init__(
        self,
        settings: Settings,
        navigation_service: NavigationService,
        form_service: FormService,
    ) -> None:
        self._settings = settings
        self._navigation = navigation_service
        self._form = form_service
        self._retry = with_retries(settings)

    async def login(self, context: BrowserContext) -> None:
        """Perform login and persist authentication in the browser context."""
        self._validate_credentials()

        page = await context.new_page()
        try:
            if self._settings.uses_token_auth:
                await self._perform_cookie_login(context, page)
            else:
                await self._retry(self._perform_password_login)(page)
            logger.info("Login completed successfully")
        except (LoginError, ElementNotFoundError, TimeoutError):
            raise
        except PlaywrightTimeoutError as exc:
            raise TimeoutError(
                "Login timed out",
                context={"url": self._settings.login_url or self._settings.base_url},
            ) from exc
        except Exception as exc:
            raise LoginError(
                "Unexpected login failure",
                context={
                    "url": self._settings.login_url or self._settings.base_url,
                    "error": str(exc),
                },
            ) from exc
        finally:
            await page.close()

    async def _perform_password_login(self, page: Page) -> None:
        """Execute the username/password login workflow."""
        await self._navigation.open_page(page, self._settings.login_url)
        await self._navigation.wait_for_selector(
            page,
            self._settings.login_username_selector,
        )

        await self._form.fill_input(page, self._settings.login_username_selector, self._settings.username)
        await self._form.fill_input(page, self._settings.login_password_selector, self._settings.password)
        await self._form.click(page, self._settings.login_submit_selector)
        await self._verify_login(page)

    async def _perform_cookie_login(self, context: BrowserContext, page: Page) -> None:
        """Set accessToken cookie and open chat until the input is ready."""
        target_url = self._settings.login_url or self._settings.base_url
        cookie_name = self._settings.token_cookie_name
        domain = self._settings.cookie_domain.lstrip(".")
        token = self._settings.access_token

        await context.clear_cookies()
        await context.add_cookies(
            [
                {
                    "name": cookie_name,
                    "value": token,
                    "domain": domain,
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax",
                },
                {
                    "name": cookie_name,
                    "value": token,
                    "domain": f".{domain}",
                    "path": "/",
                    "secure": True,
                    "httpOnly": False,
                    "sameSite": "Lax",
                },
            ]
        )
        logger.info("Cookie set: %s (domain=%s / .%s)", cookie_name, domain, domain)

        await page.goto(target_url, wait_until="domcontentloaded", timeout=self._settings.navigation_timeout)

        # Keep localStorage in sync without forcing a reload (reload can race the SPA).
        await page.evaluate(
            """([key, value]) => {
                try { localStorage.setItem(key, value); } catch (e) {}
            }""",
            [self._settings.token_storage_key, token],
        )

        # GapGPT SPA needs a moment to hydrate the chat composer.
        await page.wait_for_timeout(3000)
        await self._verify_login(page)

    async def _verify_login(self, page: Page) -> None:
        """Confirm login succeeded using the configured success selector."""
        try:
            await page.wait_for_selector(
                self._settings.login_success_selector,
                state="visible",
                timeout=self._settings.navigation_timeout,
            )
        except PlaywrightTimeoutError as exc:
            raise LoginError(
                "Login verification failed",
                context={
                    "url": page.url,
                    "success_selector": self._settings.login_success_selector,
                },
            ) from exc

    def _validate_credentials(self) -> None:
        """Ensure required credentials are configured."""
        if self._settings.uses_token_auth:
            if not self._settings.access_token:
                raise LoginError("ACCESS_TOKEN must be set when AUTH_MODE=cookie/token")
            return

        if not self._settings.username or not self._settings.password:
            raise LoginError(
                "USERNAME and PASSWORD must be set when AUTH_MODE=password",
            )
