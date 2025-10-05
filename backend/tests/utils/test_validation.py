"""Tests for validation utilities."""

import pytest

from utils.validation import (
    ValidationError,
    validate_ascii_only,
    validate_email,
    validate_password,
    validate_username,
)


class TestValidateAsciiOnly:
    """Test ASCII-only validation."""

    def test_valid_ascii_string(self):
        """Test that valid ASCII strings pass validation."""
        validate_ascii_only("hello123", "test_field")
        validate_ascii_only("user_name", "test_field")
        validate_ascii_only("test@example.com", "test_field")

    def test_invalid_non_ascii_string(self):
        """Test that non-ASCII strings fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_ascii_only("café", "test_field")
        assert "ASCII characters" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_ascii_only("naïve", "test_field")
        assert "ASCII characters" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_ascii_only("résumé", "test_field")
        assert "ASCII characters" in exc_info.value.message

    def test_empty_string(self):
        """Test that empty strings pass validation."""
        validate_ascii_only("", "test_field")


class TestValidateUsername:
    """Test username validation."""

    def test_valid_usernames(self):
        """Test that valid usernames pass validation."""
        validate_username("user123")
        validate_username("test_user")
        validate_username("admin")
        validate_username("user-name")

    def test_invalid_empty_username(self):
        """Test that empty usernames fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_username("")
        assert "cannot be empty" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_username("   ")
        assert True

    def test_invalid_short_username(self):
        """Test that short usernames fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_username("ab")
        assert "at least 3 characters" in exc_info.value.message

    def test_invalid_long_username(self):
        """Test that long usernames fail validation."""
        long_username = "a" * 256
        with pytest.raises(ValidationError) as exc_info:
            validate_username(long_username)
        assert "no more than 255 characters" in exc_info.value.message

    def test_invalid_characters_username(self):
        """Test that usernames with invalid characters fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_username("user@domain")
        assert "letters, numbers, underscores, and hyphens" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_username("user.name")
        assert True

    def test_invalid_non_ascii_username(self):
        """Test that usernames with non-ASCII characters fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_username("naïve")
        assert "ASCII characters" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_username("résumé")
        assert True


class TestValidatePassword:
    """Test password validation."""

    def test_valid_passwords(self):
        """Test that valid passwords pass validation."""
        validate_password("password123")
        validate_password("my_secret_password")
        validate_password("admin123")

    def test_invalid_empty_password(self):
        """Test that empty passwords fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password("")
        assert "cannot be empty" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_password("   ")
        assert True

    def test_invalid_short_password(self):
        """Test that short passwords fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password("12345")
        assert "at least 6 characters" in exc_info.value.message

    def test_invalid_non_ascii_password(self):
        """Test that passwords with non-ASCII characters fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_password("résumé")
        assert "ASCII characters" in exc_info.value.message


class TestValidateEmail:
    """Test email validation."""

    def test_valid_emails(self):
        """Test that valid emails pass validation."""
        validate_email("user@example.com")
        validate_email("test.user@domain.org")
        validate_email("admin@company.co.uk")

    def test_empty_email(self):
        """Test that empty emails pass validation (email is optional)."""
        validate_email("")

    def test_invalid_email_format(self):
        """Test that invalid email formats fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_email("invalid-email")
        assert "Invalid email format" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_email("user@")
        assert True

        with pytest.raises(ValidationError) as exc_info:
            validate_email("@domain.com")
        assert True

    def test_invalid_non_ascii_email(self):
        """Test that emails with non-ASCII characters fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_email("résumé@example.com")
        assert "ASCII characters" in exc_info.value.message
