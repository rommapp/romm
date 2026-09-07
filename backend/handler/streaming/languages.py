"""RomM language values reduced to the codes a broker can read."""

from typing import Any

from handler.filesystem.base_handler import LANGUAGES
from models.rom import Rom
from models.user import User

# ISO-639-1 codes for the languages RomM recognizes. rom.languages stores names
# ("French") from filename parsing and shortcodes ("fr") from metadata
# providers, so both spellings reduce to the same code here; ui_settings.locale
# stores locale codes ("pt_BR"). A broker maps what it gets to its own dialect.
_LANGUAGE_NAME_TO_ISO = {
    name.lower(): code.lower() for code, name in LANGUAGES if code.lower() != "nolang"
}
_ISO_CODES = set(_LANGUAGE_NAME_TO_ISO.values())


def language_code(value: Any) -> str | None:
    """Reduce a RomM language value to a code a broker can read, or None.

    A name resolves to its ISO-639-1 code. A locale keeps its region as a
    subtag ("pt_BR" becomes "pt-br"), which is the whole difference between
    Brazilian and European Portuguese to an emulator shipping both; a broker
    that makes nothing of the region drops it and keeps the language. Unknown
    values are omitted so a broker falls back to its own default instead of
    failing the launch.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    if normalized in _LANGUAGE_NAME_TO_ISO:
        return _LANGUAGE_NAME_TO_ISO[normalized]
    base, _, region = normalized.partition("-")
    if base not in _ISO_CODES:
        return None
    return f"{base}-{region}" if region else base


def rom_language(rom: Rom) -> str | None:
    """The ROM's own language, as the first of its languages RomM can reduce."""
    for candidate in rom.languages or []:
        code = language_code(candidate)
        if code:
            return code
    return None


def gui_language(user: User) -> str | None:
    """The user's own interface language, from their UI locale ("pt_BR")."""
    return language_code((user.ui_settings or {}).get("locale"))
