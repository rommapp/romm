from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.rom import RomFile


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
