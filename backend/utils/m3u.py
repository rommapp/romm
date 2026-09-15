from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.rom import RomFile

# Sheet formats that describe a disc by pointing at raw track files: .cue for
# BIN/CUE, .gdi for Dreamcast, .ccd for CloneCD and .mds for Alcohol. No one
# format is privileged over the others, since the tracks any of them reference
# are not loadable on their own.
DESCRIPTOR_EXTENSIONS = frozenset({"cue", "gdi", "ccd", "mds"})


def playlist_files(files: list[RomFile]) -> list[RomFile]:
    """The files of a multi-file ROM that name a playable disc.

    The .m3u itself is never one, and where descriptor files are present only
    those are, since the raw tracks they reference are not loadable on their
    own. One home for the rule: the playlist, the download endpoint and the
    disc swapper all have to agree on which files are discs.
    """
    discs = [f for f in files if f.file_extension.lower() != "m3u"]
    descriptors = [
        f for f in discs if f.file_extension.lower() in DESCRIPTOR_EXTENSIONS
    ]
    return descriptors or discs


def generate_m3u_content(
    files: list[RomFile],
    hidden_folder: bool,
) -> bytes:
    """Generate M3U playlist content for multi-file ROMs."""
    return "\n".join(
        f.file_name_for_download(hidden_folder) for f in playlist_files(files)
    ).encode()
