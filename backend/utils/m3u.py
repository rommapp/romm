from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.rom import RomFile

# Sheet formats that describe a disc by pointing at raw track files: .cue for
# BIN/CUE, .gdi for Dreamcast, .ccd for CloneCD and .mds for Alcohol. No one
# format is privileged over the others.
DESCRIPTOR_EXTENSIONS = frozenset({"cue", "gdi", "ccd", "mds"})

# The raw tracks those sheets point at, data and CDDA audio alike. None of them
# is loadable on its own, so a sheet in the set means its tracks are data rather
# than discs -- but only those tracks. Anything else present stays a disc in its
# own right. Kept in step with the shell's own list in src/main/discs/m3u.ts.
COMPANION_EXTENSIONS = frozenset(
    {"bin", "raw", "img", "sub", "mdf", "wav", "ogg", "flac", "mp3"}
)


def playlist_files(files: list[RomFile]) -> list[RomFile]:
    """The files of a multi-file ROM that name a playable disc.

    The .m3u itself is never one. Where a descriptor is present the raw tracks
    it references are not discs either, since they are not loadable alone --
    but a set is not required to be all one format, so a disc that stands on
    its own (a .chd beside a .gdi) is kept. One home for the rule: the
    playlist, the download endpoint and the disc swapper all have to agree on
    which files are discs.
    """
    discs = [f for f in files if f.file_extension.lower() != "m3u"]
    if not any(f.file_extension.lower() in DESCRIPTOR_EXTENSIONS for f in discs):
        return discs
    return [f for f in discs if f.file_extension.lower() not in COMPANION_EXTENSIONS]


def generate_m3u_content(
    files: list[RomFile],
    hidden_folder: bool,
) -> bytes:
    """Generate M3U playlist content for multi-file ROMs."""
    return "\n".join(
        f.file_name_for_download(hidden_folder) for f in playlist_files(files)
    ).encode()
