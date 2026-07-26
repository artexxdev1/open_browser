"""Automation services."""

from app.services.chat_service import ChatService
from app.services.form_service import FormService
from app.services.login_service import LoginService
from app.services.navigation_service import NavigationService

__all__ = ["ChatService", "FormService", "LoginService", "NavigationService"]
