from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from logger.formatter import highlight as hl
from logger.logger import log

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


# "(Disc 2)", "(CD 2)", TOSEC's "(Disk 1 of 2)", split "(Disc 2A)", lettered
# "(Disc B)". A letter needs a space, so "(CDi)" isn't disc 9.
DISC_TAG_REGEX = re.compile(
    r"\((?:disc|disk|cd|disque)(?:\s*([0-9]+)[a-z]?|\s+((?a:[a-z])))"
    r"(?:\s+of\s+[0-9]+)?\)",
    re.I,
)


def disc_number(file: RomFile) -> int | None:
    """The disc a file's name claims to be (A counts as 1), or None."""
    match = DISC_TAG_REGEX.search(file.file_name)
    if not match:
        return None
    number, letter = match.groups()
    return int(number) if number else ord(letter.lower()) - ord("a") + 1


def _disc_order(file: RomFile) -> tuple[bool, int, str]:
    """Sort numbered discs first and in order, then the rest by name."""
    number = disc_number(file)
    return (number is None, number or 0, file.file_name)


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
    for entry in _playlist_lines(lines):
        for candidate in _entry_candidates(entry):
            entry_path = Path(candidate)
            if not entry_path.is_absolute():
                entry_path = m3u_path.parent / entry_path
            if entry_path.is_file():
                return entry_path
        return None
    return None


def contained_playlist_entries(m3u_path: Path) -> list[str]:
    """The files an .m3u playlist lists that sit inside its own folder.

    Entries that are missing, or that resolve outside the playlist's folder
    (through `..` or an absolute path), are skipped with a warning.

    Returns:
        Each file's path relative to the playlist's folder, POSIX-separated,
        in playlist order and without duplicates or the playlist itself.
    """
    try:
        lines = m3u_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []
    root = os.path.normpath(m3u_path.parent)
    entries: list[str] = []
    for entry in _playlist_lines(lines):
        resolved = None
        contained = False
        for candidate in _entry_candidates(entry):
            normalized = os.path.normpath(os.path.join(root, candidate))
            if not normalized.startswith(root + os.sep):
                continue
            contained = True
            if os.path.isfile(normalized):
                resolved = Path(normalized).relative_to(root).as_posix()
                break
        if resolved is None:
            reason = "not found" if contained else "outside its folder"
            log.warning(
                f"Skipping playlist entry {hl(entry)} in {hl(str(m3u_path))}: {reason}"
            )
        elif resolved != m3u_path.name and resolved not in entries:
            entries.append(resolved)
    return entries


def _playlist_lines(lines: list[str]) -> list[str]:
    """A playlist's entries, without blank lines and comments."""
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


def _entry_candidates(entry: str) -> list[str]:
    """The paths a playlist entry may mean, the literal one first.

    Playlists written on Windows separate folders with backslashes, which a
    POSIX file name may also contain.
    """
    if "\\" in entry:
        return [entry, entry.replace("\\", "/")]
    return [entry]


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
