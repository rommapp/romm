"""Tests for validation utilities."""

import pytest

from utils.validation import (
    ValidationError,
    sanitize_username,
    validate_ascii_only,
    validate_email,
    validate_password,
    validate_url_for_http_request,
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
        validate_username("john.doe")
        validate_username("user@domain")
        validate_username("user+tag")
        validate_username("user/path")

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
        """Test that usernames with spaces or control characters fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_username("user name")
        assert "spaces or control characters" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_username("user\tname")
        assert "spaces or control characters" in exc_info.value.message

    def test_invalid_non_ascii_username(self):
        """Test that usernames with non-ASCII characters fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_username("naïve")
        assert "ASCII characters" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_username("résumé")
        assert "ASCII characters" in exc_info.value.message


class TestSanitizeUsername:
    """Test username sanitization."""

    def test_valid_username_unchanged(self):
        """Test that already-valid usernames are returned unchanged."""
        assert sanitize_username("user123") == "user123"
        assert sanitize_username("test_user") == "test_user"
        assert sanitize_username("user-name") == "user-name"
        assert sanitize_username("john.doe") == "john.doe"
        assert sanitize_username("user@domain") == "user@domain"

    def test_space_replaced_with_hyphen(self):
        """Test that spaces are replaced with hyphens."""
        assert sanitize_username("user name") == "user-name"
        assert sanitize_username("john doe smith") == "john-doe-smith"

    def test_consecutive_spaces_collapsed(self):
        """Test that multiple consecutive spaces collapse to a single hyphen."""
        assert sanitize_username("user  name") == "user-name"

    def test_leading_trailing_spaces_stripped(self):
        """Test that leading and trailing spaces are stripped after sanitization."""
        assert sanitize_username(" username ") == "username"

    def test_non_ascii_chars_removed(self):
        """Test that non-ASCII characters are removed."""
        assert sanitize_username("naïve") == "nave"
        assert sanitize_username("jöhn") == "jhn"

    def test_too_short_after_sanitization_raises(self):
        """Test that a ValidationError is raised if sanitized result is too short."""
        with pytest.raises(ValidationError) as exc_info:
            sanitize_username(" a ")  # strips to "a" after space→hyphen + strip
        assert "too short" in exc_info.value.message

    def test_empty_username_raises(self):
        """Test that an empty username raises a ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            sanitize_username("")
        assert "cannot be empty" in exc_info.value.message

    def test_long_username_truncated(self):
        """Test that long usernames are truncated to 255 characters."""
        long_username = "a" * 300
        result = sanitize_username(long_username)
        assert len(result) <= 255


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


class TestValidateUrlForHttpRequest:
    """Test URL validation for HTTP requests to prevent SSRF attacks."""

    def test_valid_http_urls(self):
        """Test that valid HTTP/HTTPS URLs pass validation."""
        validate_url_for_http_request("http://example.com", "test_url")
        validate_url_for_http_request("https://example.com", "test_url")
        validate_url_for_http_request("http://example.com/path", "test_url")
        validate_url_for_http_request("https://example.com/path?query=1", "test_url")
        validate_url_for_http_request("http://subdomain.example.com", "test_url")

    def test_invalid_empty_url(self):
        """Test that empty URLs fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("", "test_url")
        assert "cannot be empty" in exc_info.value.message

    def test_invalid_scheme(self):
        """Test that non-HTTP/HTTPS schemes fail validation."""
        # FTP scheme
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("ftp://example.com", "test_url")
        assert "only http and https schemes are allowed" in exc_info.value.message

        # File scheme
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("file:///etc/passwd", "test_url")
        assert "only http and https schemes are allowed" in exc_info.value.message

        # Data scheme
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("data:text/html,<h1>test</h1>", "test_url")
        assert "only http and https schemes are allowed" in exc_info.value.message

        # JavaScript scheme (XSS attack vector)
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("javascript:alert(1)", "test_url")
        assert "only http and https schemes are allowed" in exc_info.value.message

    def test_invalid_localhost(self):
        """Test that localhost and reserved hostnames fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://localhost", "test_url")
        assert (
            "localhost and reserved hostnames are not allowed" in exc_info.value.message
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://127.0.0.1", "test_url")
        assert (
            "localhost and reserved hostnames are not allowed" in exc_info.value.message
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://[::1]", "test_url")
        assert (
            "localhost and reserved hostnames are not allowed" in exc_info.value.message
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://0.0.0.0", "test_url")
        assert (
            "localhost and reserved hostnames are not allowed" in exc_info.value.message
        )

    def test_invalid_private_ipv4_addresses(self):
        """Test that private IPv4 addresses fail validation."""
        # 10.x.x.x range
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://10.0.0.1", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # 192.168.x.x range
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://192.168.1.1", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # 172.16.x.x - 172.31.x.x range
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://172.16.0.1", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://172.31.255.254", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

    def test_invalid_loopback_addresses(self):
        """Test that loopback addresses fail validation."""
        # 127.x.x.x range
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://127.0.0.2", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://127.255.255.255", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

    def test_invalid_private_ipv6_addresses(self):
        """Test that private/link-local IPv6 addresses fail validation."""
        # Link-local IPv6: fe80::/10
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://[fe80::1]", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # Unique local address: fc00::/7
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://[fc00::1]", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://[fd00::1]", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

    def test_invalid_multicast_addresses(self):
        """Test that multicast addresses fail validation."""
        # IPv4 multicast: 224.0.0.0/4
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://224.0.0.1", "test_url")
        assert "multicast addresses are not allowed" in exc_info.value.message

        # IPv6 multicast: ff00::/8
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://[ff02::1]", "test_url")
        assert "multicast addresses are not allowed" in exc_info.value.message

    def test_invalid_internal_tlds(self):
        """Test that internal TLDs fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://server.local", "test_url")
        assert "internal domain names are not allowed" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://server.internal", "test_url")
        assert "internal domain names are not allowed" in exc_info.value.message

        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://server.localhost", "test_url")
        assert "internal domain names are not allowed" in exc_info.value.message

    def test_invalid_non_standard_ip_representations(self):
        """Test that non-standard IP representations are blocked (SSRF bypass vectors)."""
        # Hexadecimal integer for 127.0.0.1
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://0x7f000001", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # Decimal integer for 127.0.0.1
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://2130706433", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # Shorthand dotted for 127.0.0.1
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://127.1", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # Hexadecimal integer for 10.0.0.1
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://0x0a000001", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # Decimal integer for 192.168.1.1
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://3232235777", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

        # Hexadecimal integer for 169.254.169.254 (cloud metadata)
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://0xa9fea9fe", "test_url")
        assert (
            "private, internal, and reserved IP addresses are not allowed"
            in exc_info.value.message
        )

    def test_invalid_missing_hostname(self):
        """Test that URLs without hostnames fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            validate_url_for_http_request("http://", "test_url")
        assert "missing hostname" in exc_info.value.message
