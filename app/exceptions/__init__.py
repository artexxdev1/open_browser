"""Custom exceptions for the automation service."""


class AutomationError(Exception):
    """Base exception for all automation errors."""

    def __init__(self, message: str, *, context: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}


class LoginError(AutomationError):
    """Raised when login fails or credentials are rejected."""


class NavigationError(AutomationError):
    """Raised when page navigation fails."""


class TimeoutError(AutomationError):
    """Raised when a Playwright operation exceeds the configured timeout."""


class ElementNotFoundError(AutomationError):
    """Raised when a required DOM element cannot be located."""
