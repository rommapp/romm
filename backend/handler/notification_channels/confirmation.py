"""The code an email channel is confirmed with, proving the address is the user's."""

import asyncio
import hashlib
import hmac
import secrets
from typing import Final

from handler.email_handler import send_email
from handler.redis_handler import async_cache

CODE_TTL_SECONDS: Final = 30 * 60
RESEND_COOLDOWN_SECONDS: Final = 60
MAX_ATTEMPTS: Final = 5


class CodeCooldownError(RuntimeError):
    """A code went out too recently to send another."""


def _key(channel_id: int, part: str) -> str:
    return f"notification-channel:{channel_id}:{part}"


def _cooldown_keys(user_id: int, address: str) -> tuple[str, str]:
    # Per user and per address rather than per channel, which a delete and a
    # re-create would reset.
    address_digest = hashlib.sha256(address.strip().lower().encode()).hexdigest()
    return (
        f"notification-channel-cooldown:user:{user_id}",
        f"notification-channel-cooldown:address:{address_digest}",
    )


def _digest(channel_id: int, code: str) -> str:
    return hashlib.sha256(f"{channel_id}:{code}".encode()).hexdigest()


async def issue_code(channel_id: int, user_id: int, address: str) -> None:
    """Email a fresh code to the address, replacing any earlier one.

    Raises:
        CodeCooldownError: A code went out to the user, or to the address, less
            than a minute ago.
        EmailError: The email could not be sent.
    """
    cooldowns = _cooldown_keys(user_id, address)
    claimed = [
        key
        for key in cooldowns
        if await async_cache.set(key, "1", ex=RESEND_COOLDOWN_SECONDS, nx=True)
    ]
    if len(claimed) < len(cooldowns):
        if claimed:
            await async_cache.delete(*claimed)
        raise CodeCooldownError("Wait a minute before asking for another code")

    code = f"{secrets.randbelow(10**6):06d}"
    await async_cache.delete(_key(channel_id, "attempts"))
    await async_cache.set(
        _key(channel_id, "code"), _digest(channel_id, code), ex=CODE_TTL_SECONDS
    )
    try:
        await asyncio.to_thread(
            send_email,
            address,
            "Your RomM confirmation code",
            f"Your code is {code}. Enter it in RomM to start getting notifications "
            f"at this address. It expires in {CODE_TTL_SECONDS // 60} minutes.\n\n"
            "If you didn't add this address to RomM, you can ignore this email.",
        )
    except Exception:
        await async_cache.delete(_key(channel_id, "code"), *cooldowns)
        raise


async def check_code(channel_id: int, code: str) -> bool:
    """Whether the code is the one last sent; a match or too many misses spends it."""
    stored = await async_cache.get(_key(channel_id, "code"))
    if not stored:
        return False

    attempts = await async_cache.incr(_key(channel_id, "attempts"))
    if attempts == 1:
        await async_cache.expire(_key(channel_id, "attempts"), CODE_TTL_SECONDS)
    if attempts > MAX_ATTEMPTS:
        await async_cache.delete(_key(channel_id, "code"))
        return False

    expected = stored.decode() if isinstance(stored, bytes) else stored
    if not hmac.compare_digest(expected, _digest(channel_id, code.strip())):
        return False
    await async_cache.delete(_key(channel_id, "code"), _key(channel_id, "attempts"))
    return True
