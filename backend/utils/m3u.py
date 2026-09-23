from __future__ import annotations

import re
from pathlib import Path
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


# The spellings a dumper writes a disc number with, as "(Disc 2)", "(CD 2)" or
# "(Disque 2)". A trailing letter covers the "(Disc 2A)" a split disc carries.
DISC_TAG_REGEX = re.compile(r"\((?:disc|disk|cd|disque)\s*([0-9]{1,2})[a-z]?\)", re.I)


def disc_number(file: RomFile) -> int | None:
    """The disc a file's name claims to be, or None when it names none."""
    match = DISC_TAG_REGEX.search(file.file_name)
    return int(match.group(1)) if match else None


def _disc_order(file: RomFile) -> tuple[int, str]:
    """Sort discs by their number, and anything unnumbered by name alone.

    Numbering is what the name cannot give: "(Disc 10)" sorts before "(Disc 2)"
    as text, and a set is free to mix "Disc 1" with "CD2".
    """
    return (disc_number(file) or 0, file.file_name)


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
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        # Playlists written on Windows separate folders with backslashes, which
        # a POSIX file name may also contain, so the literal path is tried first.
        candidates = [entry]
        if "\\" in entry:
            candidates.append(entry.replace("\\", "/"))
        for candidate in candidates:
            entry_path = Path(candidate)
            if not entry_path.is_absolute():
                entry_path = m3u_path.parent / entry_path
            if entry_path.is_file():
                return entry_path
        return None
    return None


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
    if any(f.file_extension.lower() in DESCRIPTOR_EXTENSIONS for f in discs):
        discs = [
            f for f in discs if f.file_extension.lower() not in COMPANION_EXTENSIONS
        ]
    return sorted(discs, key=_disc_order)


def generate_m3u_content(
    files: list[RomFile],
    hidden_folder: bool,
) -> bytes:
    """Generate M3U playlist content for multi-file ROMs."""
    return "\n".join(
        f.file_name_for_download(hidden_folder) for f in playlist_files(files)
    ).encode()
