import ipaddress
import re
import socket
from urllib.parse import urlparse

from logger.logger import log
from models.user import TEXT_FIELD_LENGTH


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field_name: str = "field"):
        self.message = message
        self.field_name = field_name
        super().__init__(self.message)


# Pre-compiled regex patterns for better performance
USERNAME_PATTERN = re.compile(r"^[\x21-\x7E]+$")
USERNAME_INVALID_CHARS_PATTERN = re.compile(r"[^\x21-\x7E]")
USERNAME_CONSECUTIVE_HYPHENS_PATTERN = re.compile(r"-{2,}")
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
        msg = "Username must not contain spaces or control characters"
        log.error(f"Validation failed: {msg} for username: {username}")
        raise ValidationError(msg, "Username")


def sanitize_username(username: str) -> str:
    """Sanitize a username by replacing invalid characters with hyphens.

    This is used for OIDC-provided usernames which may contain characters
    not allowed by the standard username validation rules.

    Args:
        username (str): The username to sanitize

    Returns:
        str: The sanitized username

    Raises:
        ValidationError: If the sanitized username is still invalid (e.g., too short)
    """
    if not username or not username.strip():
        msg = "Username cannot be empty"
        log.error(msg)
        raise ValidationError(msg, "Username")

    # Encode to ASCII, ignoring non-ASCII characters
    ascii_username = username.encode("ascii", errors="ignore").decode("ascii")

    # Replace any character not in [a-zA-Z0-9_-] with a hyphen
    sanitized = USERNAME_INVALID_CHARS_PATTERN.sub("-", ascii_username)

    # Collapse multiple consecutive hyphens into one
    sanitized = USERNAME_CONSECUTIVE_HYPHENS_PATTERN.sub("-", sanitized)

    # Strip leading and trailing hyphens
    sanitized = sanitized.strip("-")

    # Truncate to maximum allowed length
    sanitized = sanitized[:TEXT_FIELD_LENGTH]

    if len(sanitized) < 3:
        msg = f"Username '{username}' could not be sanitized to a valid username (result too short)"
        log.error(msg)
        raise ValidationError(msg, "Username")

    return sanitized


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


# Check for localhost and reserved hostnames
RESERVED_HOSTNAMES = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # trunk-ignore(bandit/B104)
    "::1",
    "::",
]


def validate_url_for_http_request(url: str, field_name: str = "URL") -> None:
    """Validate URL to prevent Server-Side Request Forgery (SSRF) attacks.

    This function validates that:
    - The URL scheme is http or https only
    - If the host is a literal IP address, it is not private/internal/reserved
    - The host is not a reserved hostname (localhost, 127.0.0.1, etc.)
    - The host does not use internal TLDs (.local, .internal, .localhost)

    Note: This function does NOT perform DNS resolution. Domain names that resolve
    to private IPs will not be detected (DNS rebinding/internal DNS bypass possible).
    It only checks literal IP addresses in the hostname.

    Args:
        url (str): The URL to validate
        field_name (str): The name of the field for error messages

    Raises:
        ValidationError: If the URL is invalid or potentially dangerous
    """
    if not url or not url.strip():
        msg = f"{field_name} cannot be empty"
        log.error(msg)
        raise ValidationError(msg, field_name)

    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid {field_name}: unable to parse URL"
        log.error(f"{msg}: {str(e)}")
        raise ValidationError(msg, field_name) from e

    # Validate scheme - only allow http and https
    if parsed.scheme not in ["http", "https"]:
        msg = f"Invalid {field_name}: only http and https schemes are allowed"
        log.error(f"SSRF prevention: {msg} - got scheme '{parsed.scheme}'")
        raise ValidationError(msg, field_name)

    # Extract hostname
    hostname = parsed.hostname
    if not hostname:
        msg = f"Invalid {field_name}: missing hostname"
        log.error(msg)
        raise ValidationError(msg, field_name)

    if hostname.lower() in RESERVED_HOSTNAMES:
        msg = f"Invalid {field_name}: localhost and reserved hostnames are not allowed"
        log.error(f"SSRF prevention: {msg} - hostname '{hostname}'")
        raise ValidationError(msg, field_name)

    # Try to resolve hostname as IP address
    try:
        ip = ipaddress.ip_address(hostname)

        # Block private/internal/link-local IP addresses
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            msg = f"Invalid {field_name}: private, internal, and reserved IP addresses are not allowed"
            log.error(f"SSRF prevention: {msg} - IP '{ip}'")
            raise ValidationError(msg, field_name)

        # Block multicast addresses
        if ip.is_multicast:
            msg = f"Invalid {field_name}: multicast addresses are not allowed"
            log.error(f"SSRF prevention: {msg} - IP '{ip}'")
            raise ValidationError(msg, field_name)

    except ValueError as e:
        # ipaddress.ip_address() only handles standard notation. HTTP clients
        # also accept hex integers (0x7f000001), decimal integers (2130706433),
        # shorthand dotted (127.1), and octal (0177.0.0.1). Use socket.inet_aton()
        # which handles these non-standard IPv4 representations.
        try:
            packed = socket.inet_aton(hostname)
            ip = ipaddress.IPv4Address(packed)

            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                msg = f"Invalid {field_name}: private, internal, and reserved IP addresses are not allowed"
                log.error(f"SSRF prevention: {msg} - IP '{ip}'")
                raise ValidationError(msg, field_name)

            if ip.is_multicast:
                msg = f"Invalid {field_name}: multicast addresses are not allowed"
                log.error(f"SSRF prevention: {msg} - IP '{ip}'")
                raise ValidationError(msg, field_name)

        except OSError:
            pass  # Not an IP address at all - fall through to domain name checks

        # Additional checks for suspicious domain patterns
        hostname_lower = hostname.lower()

        # Block common internal TLDs
        internal_tlds = [".local", ".internal", ".localhost"]
        if any(hostname_lower.endswith(tld) for tld in internal_tlds):
            msg = f"Invalid {field_name}: internal domain names are not allowed"
            log.error(f"SSRF prevention: {msg} - hostname '{hostname}'")
            raise ValidationError(msg, field_name) from e
