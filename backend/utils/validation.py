import re

from logger.logger import log
from models.user import TEXT_FIELD_LENGTH


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field_name: str = "field"):
        self.message = message
        self.field_name = field_name
        super().__init__(self.message)


# Pre-compiled regex patterns for better performance
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_ascii_only(value: str, field_name: str = "field") -> None:
    """Validate that a string contains only ASCII characters.

    Args:
        value (str): The value to validate
        field_name (str): The name of the field for error messages

    Raises:
        ValidationError: If the value contains non-ASCII characters
    """
    if not value:
        return

    # Check if any character is outside ASCII range (0-127)
    if any(ord(char) > 127 for char in value):
        msg = f"{field_name} must contain only ASCII characters"
        log.error(f"Validation failed: {msg}")
        raise ValidationError(msg, field_name)


def validate_username(username: str) -> None:
    """Validate username format and content.

    Args:
        username (str): The username to validate

    Raises:
        ValidationError: If the username is invalid
    """
    if not username or not username.strip():
        msg = "Username cannot be empty"
        log.error(msg)
        raise ValidationError(msg, "Username")

    validate_ascii_only(username, "Username")

    if len(username) < 3:
        msg = "Username must be at least 3 characters long"
        log.error(msg)
        raise ValidationError(msg, "Username")

    if len(username) > TEXT_FIELD_LENGTH:
        msg = "Username must be no more than 255 characters long"
        log.error(msg)
        raise ValidationError(msg, "Username")

    if not USERNAME_PATTERN.match(username):
        msg = "Username can only contain letters, numbers, underscores, and hyphens"
        log.error(f"Validation failed: {msg} for username: {username}")
        raise ValidationError(msg, "Username")


def validate_password(password: str) -> None:
    """Validate password format and content.

    Args:
        password (str): The password to validate

    Raises:
        ValidationError: If the password is invalid
    """
    if not password or not password.strip():
        msg = "Password cannot be empty"
        log.error(msg)
        raise ValidationError(msg, "Password")

    validate_ascii_only(password, "Password")

    if len(password) < 6:
        msg = "Password must be at least 6 characters long"
        log.error(msg)
        raise ValidationError(msg, "Password")

    if len(password) > TEXT_FIELD_LENGTH:
        msg = "Password must be no more than 255 characters long"
        log.error(msg)
        raise ValidationError(msg, "Password")


def validate_email(email: str) -> None:
    """Validate email format and content.

    Args:
        email (str): The email to validate

    Raises:
        ValidationError: If the email is invalid
    """
    if not email:
        return

    validate_ascii_only(email, "Email")

    if not EMAIL_PATTERN.match(email):
        msg = "Invalid email format"
        log.error(f"Validation failed: {msg} for email: {email}")
        raise ValidationError(msg, "Email")
