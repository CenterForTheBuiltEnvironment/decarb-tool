from typing import TypeVar

from dash_iconify import DashIconify

from utils.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


# --- Exception Classes for Error Handling --- #


class CallbackError(Exception):
    """Base exception for callback errors with user-friendly messages."""

    def __init__(self, user_message: str, technical_details: str = ""):
        self.user_message = user_message
        self.technical_details = technical_details
        super().__init__(user_message)


class DataNotFoundError(CallbackError):
    """Data required for operation not found."""

    pass


class ValidationError(CallbackError):
    """Input validation failed."""

    pass


class CalculationError(CallbackError):
    """Calculation or processing failed."""

    pass


# --- Decorator for Error Handling in Callbacks --- #
# Create the dict format that Mantine NotificationContainer expects
def create_error_notification(
    title: str,
    message: str,
    notification_id: str = "error-notification",
) -> dict:
    """Create a Mantine notification for errors (red)."""
    return {
        "id": notification_id,
        "title": title,
        "message": message,
        "color": "red",
        "loading": False,
        "action": "show",
        "autoClose": 5000,
        "icon": DashIconify(icon="mdi:alert-circle-outline"),
    }


def create_warning_notification(
    title: str,
    message: str,
    notification_id: str = "warning-notification",
) -> dict:
    """Create a Mantine notification for warnings (yellow)."""
    return {
        "id": notification_id,
        "title": title,
        "message": message,
        "color": "yellow",
        "loading": False,
        "action": "show",
        "autoClose": 4000,
        "icon": DashIconify(icon="mdi:alert-outline"),
    }


def create_success_notification(
    title: str,
    message: str,
    notification_id: str = "success-notification",
) -> dict:
    """Create a Mantine notification for success (green)."""
    return {
        "id": notification_id,
        "title": title,
        "message": message,
        "color": "green",
        "loading": False,
        "action": "show",
        "autoClose": 3000,
        "icon": DashIconify(icon="mdi:check-circle-outline"),
    }


def create_info_notification(
    title: str,
    message: str,
    notification_id: str = "info-notification",
) -> dict:
    """Create a Mantine notification for informational messages (blue)."""
    return {
        "id": notification_id,
        "title": title,
        "message": message,
        "color": "blue",
        "loading": False,
        "action": "show",
        "autoClose": 3000,
        "icon": DashIconify(icon="mdi:information-outline"),
    }
