import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from logger.logger import log
from models.rom import Rom, RomFile, RomFileCategory
from utils.filesystem import COMPRESSED_FILE_SUFFIXES
from utils.m3u import first_playlist_entry, playlist_discs
from utils.platform_slugs import UniversalPlatformSlug as UPS

try:
    import sigil
except ImportError:
    sigil = None

# The platforms sigil reads a title id or save identity from at scan time.
SIGIL_EXTRACT_PLATFORM_SLUGS: Final[dict[str, str]] = {
    UPS.PSP: "psp",
    UPS.PSX: "psx",
    UPS.PS2: "ps2",
    UPS.PSVITA: "psvita",
    UPS.SWITCH: "switch",
    UPS.SWITCH_2: "switch",
    UPS.N3DS: "3ds",
    UPS.WII: "wii",
    UPS.WIIU: "wiiu",
    UPS.NGC: "gamecube",
    UPS.DC: "dreamcast",
    UPS.PS3: "ps3",
    UPS.XBOX: "xbox",
    UPS.XBOX360: "xbox360",
    UPS.N64: "n64",
    UPS.GB: "gb",
    UPS.GBC: "gbc",
}

# Sigil reads these titles but can't collect or restore their saves.
_EXTRACT_ONLY_PLATFORM_SLUGS: Final = frozenset({UPS.XBOX, UPS.XBOX360})

# The platforms sigil collects and restores saves for. Saturn and Sega CD saves
# carry no title id, so sigil restores them without one.
SIGIL_RESTORE_PLATFORM_SLUGS: Final[dict[str, str]] = {
    **{
        slug: sigil_slug
        for slug, sigil_slug in SIGIL_EXTRACT_PLATFORM_SLUGS.items()
        if slug not in _EXTRACT_ONLY_PLATFORM_SLUGS
    },
    UPS.SATURN: "saturn",
    UPS.SEGACD: "segacd",
}

# Cartridge platforms with no sigil converter, whose stored save is already the
# file every emulator for them reads.
NATIVE_SAVE_PLATFORM_SLUGS: Final = frozenset(
    {
        UPS.NES,
        UPS.FAMICOM,
        UPS.SNES,
        UPS.SFAM,
        UPS.GENESIS,
        UPS.SMS,
        UPS.GAMEGEAR,
        UPS.SEGA32,
        UPS.GBA,
        UPS.NDS,
    }
)

# The Switch family in RomM's own terms. Its headers need prod.keys to decrypt,
# and it is the only family whose files may carry their title id in the filename.
SWITCH_PLATFORM_SLUGS: Final = frozenset({UPS.SWITCH, UPS.SWITCH_2})


def sigil_binding() -> Any:
    """The `sigil` module, or None when this build has no binding."""
    return sigil


def _is_routine_error(exc: Exception) -> bool:
    """Whether the error is expected for an arbitrary library file: no title id,
    a format sigil can't parse, or missing decryption keys."""
    return sigil is not None and isinstance(
        exc,
        (
            sigil.SigilNotFoundError,
            sigil.SigilUnsupportedFormatError,
            sigil.SigilNeedsKeyError,
        ),
    )


@dataclass(frozen=True)
class SigilUnitMember:
    """One file of an unpacked save unit, as sigil hashes it."""

    name: str
    is_clock: bool


@dataclass(frozen=True)
class SigilExtractionResult:
    title_id: str
    save_target: str
    usage: str
    content_type: str | None = None
    version: int | None = None
    raw_serial: str = ""
    features: int = 0
    n64_header: str = ""
    n64_md5: str = ""
    n64_md5_n64: str = ""
    # Each listed disc's title id, disc 1 first, when the file read is a playlist.
    playlist_title_ids: tuple[str, ...] | None = None


@dataclass(frozen=True)
class SigilGame:
    """A ROM's game as sigil's collect and restore take it."""

    result: "sigil.SigilResult"
    # Every id the game's saves may carry: each disc's title id, disc 1 first.
    game_ids: tuple[str, ...]


class SigilService:
    """Service to extract platform-native title ids from ROM binaries via the
    optional `sigil` cffi binding."""

    @classmethod
    def is_enabled(cls) -> bool:
        """Whether this build can read title ids at all.

        The results alone can't say: an absent binding looks like a file with
        no title id.
        """
        return sigil is not None

    def unit_hashes(
        self, root: Path, members: list[SigilUnitMember], archived: bool
    ) -> tuple[str, str] | None:
        """Sigil's content and identity hash of a save unit unpacked under
        `root`, or None without the binding or when sigil can't read it.

        Args:
            archived: whether the unit travels as a zip; a lone raw file doesn't.
        """
        if sigil is None or not members:
            return None
        unit = sigil.SigilSaveUnit(
            key=root.name,
            shape="multi" if archived else "single",
            members=tuple(
                sigil.SigilSaveMember(
                    path=member.name,
                    entry=member.name,
                    role="rtc" if member.is_clock else "primary",
                    present=True,
                )
                for member in sorted(members, key=lambda m: m.name)
            ),
            expected=(),
            unkeyed=(),
            artifact=root.name,
            content_hash="",
            identity_hash="",
        )
        try:
            hashed = sigil.hash_saves(unit, root)
        except Exception as exc:
            log.error(f"Sigil could not hash the save unit under {root}: {exc}")
            return None
        return hashed.content_hash, hashed.identity_hash

    async def extract_title_id(
        self,
        platform_slug: str,
        file_path: str,
    ) -> SigilExtractionResult | None:
        if sigil is None:
            return None

        sigil_slug = SIGIL_EXTRACT_PLATFORM_SLUGS.get(platform_slug)
        if sigil_slug is None:
            return None

        if not file_path.lower().endswith(".m3u"):
            result = await self._extract(sigil_slug, file_path)
            return self._extraction(result) if result else None

        # A playlist is identified by its first disc, and lists the rest.
        playlist = Path(file_path)
        entry = await asyncio.to_thread(first_playlist_entry, playlist)
        if entry is None:
            return None
        result = await self._extract(sigil_slug, str(entry))
        if result is None:
            return None
        title_ids = [result.title_id]
        for disc in await asyncio.to_thread(playlist_discs, playlist):
            if disc != entry and (other := await self._extract(sigil_slug, str(disc))):
                title_ids.append(other.title_id)
        return replace(
            self._extraction(result),
            playlist_title_ids=tuple(t for t in title_ids if t),
        )

    @staticmethod
    async def _extract(sigil_slug: str, file_path: str) -> "sigil.SigilResult | None":
        # Sigil reads a binary, never the container holding one.
        if file_path.lower().endswith(COMPRESSED_FILE_SUFFIXES):
            return None
        try:
            return await asyncio.to_thread(
                sigil.extract, file_path, platform=sigil_slug, filename_fallback=False
            )
        except Exception as exc:
            if _is_routine_error(exc):
                log.debug(f"Sigil found no title id for {file_path}: {exc}")
            else:
                log.error(f"Sigil extraction failed for {file_path}: {exc}")
            return None

    @staticmethod
    def _extraction(result: "sigil.SigilResult") -> SigilExtractionResult:
        raw_content_type = getattr(result, "switch_content_type", None)
        content_type = (
            raw_content_type if raw_content_type not in (None, "", "unknown") else None
        )

        return SigilExtractionResult(
            title_id=result.title_id,
            # sigil calls this save_id; RomM's name for it is save_target.
            save_target=result.save_id,
            usage=result.usage,
            content_type=content_type,
            # Version 0 is a valid base-game version, so keep the int as-is;
            # a missing field (non-Switch, older binding) maps to None.
            version=getattr(result, "title_version", None),
            raw_serial=result.raw_serial,
            features=result.features,
            n64_header=result.n64_header,
            n64_md5=result.n64_md5,
            n64_md5_n64=result.n64_md5_n64,
        )

    @staticmethod
    def stored_game(rom: Rom, rom_files: Iterable[RomFile]) -> SigilGame | None:
        """Rebuild the game sigil identified at scan time from the stored columns.

        The identity sigil read per file comes from the file holding the ROM's
        title id (any read file on a platform without one), defaulting as a
        fresh extraction would until a rescan reads one.

        Returns:
            None when the binding is absent or sigil restores no saves for the
            ROM's platform.
        """
        sigil_slug = SIGIL_RESTORE_PLATFORM_SLUGS.get(rom.platform_slug)
        if sigil is None or sigil_slug is None:
            return None

        own_files = sorted(
            (f for f in rom_files if f.category in (None, RomFileCategory.GAME)),
            key=lambda f: f.listing_order,
        )
        source = next(
            (
                f
                for f in own_files
                if f.sigil_features is not None
                and (f.title_id or None) == (rom.title_id or None)
            ),
            None,
        )
        game_ids = dict.fromkeys(
            title_id
            for title_id in (
                rom.title_id,
                *(f.title_id for f in own_files),
                *(t for f in own_files for t in f.playlist_title_ids or ()),
            )
            if title_id
        )
        return SigilGame(
            result=sigil.SigilResult.persisted(
                platform=sigil_slug,
                title_id=rom.title_id or "",
                save_id=rom.save_target or "",
                features=source.sigil_features if source else 0,
                raw_serial=(source.raw_serial or "") if source else "",
                n64_header=(source.n64_header or "") if source else "",
                n64_md5=(source.n64_md5 or "") if source else "",
                n64_md5_n64=(source.n64_md5_n64 or "") if source else "",
            ),
            game_ids=tuple(game_ids),
        )
