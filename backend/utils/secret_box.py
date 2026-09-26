"""Symmetric sealing of small secrets kept in the database, keyed off the auth secret."""

import base64
import hashlib
import json
from functools import cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from config import ROMM_AUTH_SECRET_KEY


class UnsealError(ValueError):
    """The value was sealed with another key, or is not a sealed value."""


@cache
def _fernet() -> Fernet:
    # Derived rather than the raw secret, so the key serves this purpose only.
    digest = hashlib.sha256(f"romm:secret-box:{ROMM_AUTH_SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(value: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(value).encode()).decode()


def unseal(token: str) -> dict[str, Any]:
    """Open a value `seal` produced.

    Raises:
        UnsealError: ROMM_AUTH_SECRET_KEY changed since it was sealed, or the
            value was never sealed.
    """
    try:
        value = json.loads(_fernet().decrypt(token.encode()))
    except (InvalidToken, ValueError) as exc:
        raise UnsealError("Could not unseal the value") from exc
    if not isinstance(value, dict):
        raise UnsealError("The sealed value is not an object")
    return value
