"""A whole memory card pushed as one game's save, cut down to that game's saves.

A client without sigil may push the card every game shares. Stored as given,
it would hand out every game's saves and change whenever any game writes.
"""

from dataclasses import replace

from adapters.services.sigil import SIGIL_RESTORE_PLATFORM_SLUGS, SigilService
from adapters.services.sigil_card import (
    CardContents,
    CardSplitError,
    game_card,
    splits_cards,
)
from handler.database import db_rom_handler
from handler.snapshots.manifest import SaveEntry
from handler.snapshots.write import (
    SAVE_PART,
    ContentMismatch,
    SnapshotWrite,
    part_bytes,
)
from logger.logger import log
from models.assets import SaveFormat, SaveShape
from utils.memory_cards import content_hash_of_bytes


async def own_saves_only(write: SnapshotWrite) -> SnapshotWrite:
    """The push with a native card holding other games' saves replaced by the
    game's per-game unit, in sigil's neutral form.

    A card holding only the game's saves, or none of them, stays as sent, and so
    does every save when sigil is absent or fails.

    Raises:
        ContentMismatch: the card sent doesn't hash to the manifest's value.
    """
    entry = write.manifest.save
    part = write.parts.get(SAVE_PART)
    sigil_platform = SIGIL_RESTORE_PLATFORM_SLUGS.get(write.rom.platform_slug)
    if (
        not isinstance(entry, SaveEntry)
        or entry.format != SaveFormat.NATIVE
        or entry.shape != SaveShape.SINGLE
        or part is None
        or part.content is None
        or not splits_cards(sigil_platform)
    ):
        return write

    game = SigilService.stored_game(
        write.rom, db_rom_handler.rom_files_for_rom_id(write.rom.id)
    )
    if game is None:
        log.warning(
            f"Stored the card pushed for ROM {write.rom.id} as sent: sigil isn't installed"
        )
        return write
    content_path = write.rom_file.file_name if write.rom_file else write.rom.fs_name
    card = part_bytes(part.content)
    try:
        found = await game_card(card, game, content_path)
    except CardSplitError as exc:
        log.warning(f"Stored the card pushed for ROM {write.rom.id} as sent: {exc}")
        return write
    if found.contents == CardContents.NONE_OF_THE_GAMES:
        log.info(
            f"Stored the card pushed for ROM {write.rom.id} as sent: none of its "
            f"{found.saves_on_card} saves carries the game's ids {game.game_ids}"
        )
    if found.contents != CardContents.OTHER_GAMES_TOO:
        return write

    assert found.unit is not None
    if content_hash_of_bytes(card) != entry.hash:
        raise ContentMismatch(SAVE_PART)
    unit_hash = content_hash_of_bytes(found.unit)
    if unit_hash is None:
        log.warning(
            f"Stored the card pushed for ROM {write.rom.id} as sent: its unit didn't hash"
        )
        return write
    return replace(
        write,
        manifest=replace(
            write.manifest,
            save=SaveEntry(
                hash=unit_hash,
                shape=SaveShape.MULTI if found.shape == "multi" else SaveShape.SINGLE,
                format=SaveFormat.NEUTRAL,
            ),
        ),
        parts={
            **write.parts,
            SAVE_PART: replace(part, content=found.unit, file_name=found.artifact),
        },
    )
