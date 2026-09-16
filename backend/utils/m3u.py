from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.rom import RomFile


def first_playlist_entry(m3u_path: Path) -> Path | None:
    """Resolve an .m3u playlist to the first disc file it lists.

    Returns:
        The first non-comment entry, relative to the playlist's folder unless
        absolute, or None when the playlist can't be read or that entry isn't
        a file on disk.
    """
    try:
        lines = m3u_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        # Playlists written on Windows separate folders with backslashes.
        entry = line.strip().replace("\\", "/")
        if not entry or entry.startswith("#"):
            continue
        entry_path = Path(entry)
        if not entry_path.is_absolute():
            entry_path = m3u_path.parent / entry_path
        try:
            return entry_path if entry_path.is_file() else None
        except OSError:
            return None
    return None


def playlist_files(files: list[RomFile]) -> list[RomFile]:
    """The files of a multi-file ROM that name a playable disc.

    The .m3u itself is never one, and where .cue files are present only those
    are, since the raw .bin tracks they reference are not loadable on their own.
    One home for the rule: the playlist, the download endpoint and the disc
    swapper all have to agree on which files are discs.
    """
    discs = [f for f in files if f.file_extension.lower() != "m3u"]
    cue_files = [f for f in discs if f.file_extension.lower() == "cue"]
    return cue_files or discs


def generate_m3u_content(
    files: list[RomFile],
    hidden_folder: bool,
) -> bytes:
    """Generate M3U playlist content for multi-file ROMs."""
    return "\n".join(
        f.file_name_for_download(hidden_folder) for f in playlist_files(files)
    ).encode()
