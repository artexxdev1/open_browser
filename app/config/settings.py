"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Parse an integer environment variable."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _env_path(name: str, default: Path) -> Path:
    """Parse a path environment variable relative to the project root."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    headless: bool
    base_url: str
    login_url: str
    auth_mode: str
    username: str
    password: str
    access_token: str
    token_storage_key: str
    timeout: int
    navigation_timeout: int
    login_username_selector: str
    login_password_selector: str
    login_submit_selector: str
    login_success_selector: str
    session_expired_selector: str
    chat_input_selector: str
    chat_submit_selector: str
    chat_answer_selector: str
    answer_timeout: int
    test_message: str
    storage_state_path: Path
    log_dir: Path
    log_level: str
    retry_max_attempts: int
    retry_min_wait_seconds: float
    retry_max_wait_seconds: float

    @property
    def uses_token_auth(self) -> bool:
        """Return True when authentication uses an access token."""
        return self.auth_mode.lower() == "token"

    @property
    def browser_args(self) -> list[str]:
        """Chromium launch arguments optimized for container deployments."""
        return [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=TranslateUI",
            "--mute-audio",
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings(
        headless=_env_bool("HEADLESS", default=True),
        base_url=os.getenv("BASE_URL", "").strip(),
        login_url=os.getenv("LOGIN_URL", "").strip(),
        auth_mode=os.getenv("AUTH_MODE", "password").strip().lower(),
        username=os.getenv("USERNAME", "").strip(),
        password=os.getenv("PASSWORD", "").strip(),
        access_token=os.getenv("ACCESS_TOKEN", "").strip(),
        token_storage_key=os.getenv("TOKEN_STORAGE_KEY", "accessToken"),
        timeout=_env_int("TIMEOUT", 30_000),
        navigation_timeout=_env_int("NAVIGATION_TIMEOUT", 60_000),
        login_username_selector=os.getenv("LOGIN_USERNAME_SELECTOR", "#username"),
        login_password_selector=os.getenv("LOGIN_PASSWORD_SELECTOR", "#password"),
        login_submit_selector=os.getenv("LOGIN_SUBMIT_SELECTOR", 'button[type="submit"]'),
        login_success_selector=os.getenv("LOGIN_SUCCESS_SELECTOR", ".dashboard"),
        session_expired_selector=os.getenv("SESSION_EXPIRED_SELECTOR", 'a[href="/login"]'),
        chat_input_selector=os.getenv(
            "CHAT_INPUT_SELECTOR",
            "textarea.q-field__native.bidi-textarea",
        ),
        chat_submit_selector=os.getenv("CHAT_SUBMIT_SELECTOR", "button.submit-btn-v2"),
        chat_answer_selector=os.getenv(
            "CHAT_ANSWER_SELECTOR",
            ".q-message-text--received .q-message-text-content",
        ),
        answer_timeout=_env_int("ANSWER_TIMEOUT", 120_000),
        test_message=os.getenv("TEST_MESSAGE", "Hello, this is a test message."),
        storage_state_path=_env_path("STORAGE_STATE_PATH", PROJECT_ROOT / "storage" / "state.json"),
        log_dir=_env_path("LOG_DIR", PROJECT_ROOT / "storage" / "logs"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        retry_max_attempts=_env_int("RETRY_MAX_ATTEMPTS", 3),
        retry_min_wait_seconds=float(os.getenv("RETRY_MIN_WAIT_SECONDS", "1")),
        retry_max_wait_seconds=float(os.getenv("RETRY_MAX_WAIT_SECONDS", "10")),
    )
