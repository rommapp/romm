"""Validation utilities for user input."""

import re

from fastapi import HTTPException, status

from logger.logger import log


def validate_ascii_only(value: str, field_name: str = "field") -> None:
    """Validate that a string contains only ASCII characters.

    Args:
        value (str): The value to validate
        field_name (str): The name of the field for error messages

    Raises:
        HTTPException: If the value contains non-ASCII characters
    """
    if not value:
        return

    # Check if any character is outside ASCII range (0-127)
    if any(ord(char) > 127 for char in value):
        msg = f"{field_name} must contain only ASCII characters"
        log.error(f"Validation failed: {msg} for value: {value}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


def validate_username(username: str) -> None:
    """Validate username format and content.

    Args:
        username (str): The username to validate

    Raises:
        HTTPException: If the username is invalid
    """
    if not username or not username.strip():
        msg = "Username cannot be empty"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Check for ASCII-only characters
    validate_ascii_only(username, "Username")

    # Additional username validation rules
    if len(username) < 3:
        msg = "Username must be at least 3 characters long"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    if len(username) > 50:
        msg = "Username must be no more than 50 characters long"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r"^[a-zA-Z0-9_-]+$", username):
        msg = "Username can only contain letters, numbers, underscores, and hyphens"
        log.error(f"Validation failed: {msg} for username: {username}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


def validate_password(password: str) -> None:
    """Validate password format and content.

    Args:
        password (str): The password to validate

    Raises:
        HTTPException: If the password is invalid
    """
    if not password or not password.strip():
        msg = "Password cannot be empty"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # Check for ASCII-only characters
    validate_ascii_only(password, "Password")

    # Additional password validation rules
    if len(password) < 6:
        msg = "Password must be at least 6 characters long"
        log.error(msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


def validate_email(email: str) -> None:
    """Validate email format and content.

    Args:
        email (str): The email to validate

    Raises:
        HTTPException: If the email is invalid
    """
    if not email:
        return  # Email is optional

    # Check for ASCII-only characters
    validate_ascii_only(email, "Email")

    # Basic email format validation
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        msg = "Invalid email format"
        log.error(f"Validation failed: {msg} for email: {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
