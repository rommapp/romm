"""Switch title-id knowledge: recognising a base-game id, recovering one from an
update or DLC id, and mapping a content type to a file category."""

import re
from typing import Final

from models.rom import RomFileCategory

# Maps sigil's Switch CNMT content type to the RomFile category. Authoritative
# over folder-derived categories when the binary parse succeeds.
CONTENT_TYPE_CATEGORIES: Final[dict[str, RomFileCategory]] = {
    "application": RomFileCategory.GAME,
    "patch": RomFileCategory.UPDATE,
    "addon": RomFileCategory.DLC,
}

TITLE_ID_REGEX: Final = re.compile(r"[0-9A-Fa-f]{16}")
# An already-embedded id, e.g. [0100F4700B2E0000].
TITLE_ID_BRACKET_REGEX: Final = re.compile(rf"\[{TITLE_ID_REGEX.pattern}\]")


def derive_base_title_id(title_id: str) -> str | None:
    """Derive the base-game title id from an update/DLC id: clear the low 12
    bits and decrement the program-index nibble when it is odd."""
    if len(title_id) < 4:
        return None
    nibble_char = title_id[-4]
    try:
        nibble = int(nibble_char, 16)
    except ValueError:
        return None
    if nibble % 2 == 1:
        nibble -= 1
    formatted = format(nibble, "x" if nibble_char.islower() else "X")
    return f"{title_id[:-4]}{formatted}000"


def is_base_title_id(title_id: str) -> bool:
    """A base-game id is its own derived base."""
    return derive_base_title_id(title_id) == title_id
