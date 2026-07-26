"""Domain models for session and site configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SessionState:
    """Metadata about a persisted browser session."""

    path: Path
    exists: bool

    @property
    def is_available(self) -> bool:
        """Return True when a session file is present on disk."""
        return self.exists and self.path.is_file()


@dataclass(frozen=True)
class SiteConfig:
    """Site-specific selectors and URLs for future multi-site support."""

    name: str
    base_url: str
    login_url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    success_selector: str
    expired_selector: str
