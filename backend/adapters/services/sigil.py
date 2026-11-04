import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from logger.formatter import highlight as hl
from logger.logger import log
from utils.filesystem import COMPRESSED_FILE_SUFFIXES
from utils.m3u import first_playlist_entry
from utils.platform_slugs import UniversalPlatformSlug as UPS

try:
    import sigil
except ImportError:
    sigil = None

SIGIL_PLATFORM_SLUGS: Final[dict[str, str]] = {
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
}

# The Switch family in RomM's own terms. Its headers need prod.keys to decrypt,
# and it is the only family whose files may carry their title id in the filename.
SWITCH_PLATFORM_SLUGS: Final = frozenset({UPS.SWITCH, UPS.SWITCH_2})

# Files the current scan skipped because RomM holds no keys for their headers.
# A context var, so scans overlapping in one process (DEV_MODE) keep their own.
_needs_key_paths: ContextVar[set[str] | None] = ContextVar(
    "sigil_needs_key_paths", default=None
)


def begin_scan() -> None:
    _needs_key_paths.set(set())


def log_scan_summary() -> None:
    """Say how many encrypted Switch files this scan left without a title id."""
    paths = _needs_key_paths.get()
    if not paths:
        return
    log.info(
        f"{hl(str(len(paths)))} encrypted Switch files got no title id: "
        "RomM doesn't decrypt Switch files. Decrypted dumps, or a client "
        "holding your keys, can identify them."
    )


@dataclass(frozen=True)
class SigilExtractionResult:
    title_id: str
    save_target: str
    usage: str
    content_type: str | None = None
    version: int | None = None


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

    async def extract_title_id(
        self,
        platform_slug: str,
        file_path: str,
    ) -> SigilExtractionResult | None:
        if sigil is None:
            return None

        sigil_slug = SIGIL_PLATFORM_SLUGS.get(platform_slug)
        if sigil_slug is None:
            return None

        # A playlist is identified by its first disc.
        if file_path.lower().endswith(".m3u"):
            entry = await asyncio.to_thread(first_playlist_entry, Path(file_path))
            if entry is None:
                return None
            file_path = str(entry)

        # Sigil reads a binary, never the container holding one.
        if file_path.lower().endswith(COMPRESSED_FILE_SUFFIXES):
            return None

        try:
            result = await asyncio.to_thread(
                sigil.extract, file_path, platform=sigil_slug, filename_fallback=False
            )
        # A Switch header RomM holds no keys for, reported in the scan summary.
        except sigil.SigilNeedsKeyError as exc:
            if (paths := _needs_key_paths.get()) is not None:
                paths.add(file_path)
            log.debug(f"Sigil found no title id for {file_path}: {exc}")
            return None
        # Expected for arbitrary library files: no title id or a format sigil can't parse.
        except (
            sigil.SigilNotFoundError,
            sigil.SigilUnsupportedFormatError,
        ) as exc:
            log.debug(f"Sigil found no title id for {file_path}: {exc}")
            return None
        except Exception as exc:
            log.error(f"Sigil extraction failed for {file_path}: {exc}")
            return None

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
        )
