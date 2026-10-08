"""One game's saves split off a memory card every game shares, through sigil."""

import asyncio
import enum
import io
import os
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

from adapters.services.sigil import SigilGame, sigil_binding


@dataclass(frozen=True)
class _SharedCardLayout:
    """A layout that keeps every game's saves on one card, as sigil's rows name it."""

    core: str
    options: Mapping[str, str]
    # Dolphin picks the card's folder by the disc's region, so the card goes under each.
    paths: tuple[str, ...]


# Sigil platforms whose cards carry each save's game id, so a save's owner is known.
_SHARED_CARD_LAYOUTS: Final[dict[str, _SharedCardLayout]] = {
    "psx": _SharedCardLayout(
        "pcsx_rearmed", {"pcsx_rearmed_memcard1": "shared"}, ("pcsx-card1.mcd",)
    ),
    "ps2": _SharedCardLayout(
        "pcsx2", {"pcsx2_shared_memory_cards": "enabled"}, ("Mcd001.ps2",)
    ),
    "gamecube": _SharedCardLayout(
        "dolphin",
        {"SlotA": "1"},
        tuple(f"User/GC/MemoryCardA.{region}.raw" for region in ("USA", "EUR", "JAP")),
    ),
}


class CardContents(enum.Enum):
    NOT_A_CARD = "not_a_card"
    ONLY_THE_GAMES = "only_the_games"
    NONE_OF_THE_GAMES = "none_of_the_games"
    OTHER_GAMES_TOO = "other_games_too"


@dataclass(frozen=True)
class GameCard:
    """What a card holds for one game, and, when it holds other games' saves
    too, the game's saves alone as the unit sigil collects for it."""

    contents: CardContents
    saves_on_card: int = 0
    unit: bytes | None = None
    shape: Literal["single", "multi"] | None = None
    artifact: str = ""


class CardSplitError(Exception):
    """Sigil couldn't read the card or collect the game's saves from it."""


def splits_cards(sigil_platform: str | None) -> bool:
    """Whether a card of this sigil platform names each save's game."""
    return sigil_platform in _SHARED_CARD_LAYOUTS


def _saves_in_unit(binding: Any, unit: bytes, scratch: Path) -> int:
    if zipfile.is_zipfile(io.BytesIO(unit)):
        with zipfile.ZipFile(io.BytesIO(unit)) as zf:
            return sum(1 for info in zf.infolist() if not info.is_dir())
    path = scratch / "unit"
    path.write_bytes(unit)
    try:
        return len(binding.list_card(path).entries)
    except binding.SigilUnsupportedFormatError:
        # A lone GameCube save file, which isn't a card.
        return 1


def _game_card(card: bytes, game: SigilGame, content_path: str) -> GameCard:
    binding = sigil_binding()
    if binding is None:
        raise CardSplitError("sigil isn't installed")
    layout = _SHARED_CARD_LAYOUTS[game.result.platform]
    with tempfile.TemporaryDirectory(prefix="romm-card-") as tmp:
        scratch = Path(tmp, "scratch")
        scratch.mkdir()
        listed = scratch / "card"
        listed.write_bytes(card)
        try:
            entries = len(binding.list_card(listed).entries)
        except binding.SigilUnsupportedFormatError:
            return GameCard(CardContents.NOT_A_CARD)
        except binding.SigilError as exc:
            raise CardSplitError(f"sigil couldn't list the card: {exc}") from exc
        if entries == 0:
            return GameCard(CardContents.NONE_OF_THE_GAMES)

        root = Path(tmp, "root")
        for relative in layout.paths:
            placed = root / relative
            placed.parent.mkdir(parents=True, exist_ok=True)
            os.link(listed, placed)
        try:
            collected = binding.collect(
                game.result,
                layout.core,
                content_path,
                root,
                options=dict(layout.options),
                game_ids=game.game_ids,
                mode="unmanaged",
            )
            unit = collected.data
            kept = _saves_in_unit(binding, unit, scratch) if unit else 0
        except binding.SigilError as exc:
            raise CardSplitError(
                f"sigil couldn't collect the game's saves: {exc}"
            ) from exc

    if unit is None or kept == 0:
        return GameCard(CardContents.NONE_OF_THE_GAMES, entries)
    if kept == entries:
        return GameCard(CardContents.ONLY_THE_GAMES, entries)
    return GameCard(
        CardContents.OTHER_GAMES_TOO,
        entries,
        unit=unit,
        shape="multi" if collected.shape == "multi" else "single",
        artifact=collected.artifact,
    )


async def game_card(card: bytes, game: SigilGame, content_path: str) -> GameCard:
    """Sort a card by whose saves it holds, and collect `game`'s from it when
    other games' saves sit beside them.

    Args:
        game: a game whose sigil platform `splits_cards`.
        content_path: the ROM file name the unit is named after.

    Raises:
        CardSplitError: sigil is absent, or couldn't read the card or collect from it.
    """
    return await asyncio.to_thread(_game_card, card, game, content_path)
