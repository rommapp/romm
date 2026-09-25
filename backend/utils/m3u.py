from __future__ import annotations

import os
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


def _playlist_entries(m3u_path: Path) -> list[list[Path]] | None:
    """Each disc line's possible paths, literal first since a POSIX name may
    hold the backslashes Windows playlists separate folders with."""
    try:
        lines = m3u_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return None
    entries = []
    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        candidates = [entry]
        if "\\" in entry:
            candidates.append(entry.replace("\\", "/"))
        entries.append(
            [
                path if path.is_absolute() else m3u_path.parent / path
                for path in map(Path, candidates)
            ]
        )
    return entries


def first_playlist_entry(m3u_path: Path) -> Path | None:
    """Resolve an .m3u playlist to the first disc file it lists.

    Returns:
        The first entry's path, or None when the playlist can't be read or that
        entry isn't a file on disk.
    """
    entries = _playlist_entries(m3u_path)
    if not entries:
        return None
    return next((path for path in entries[0] if path.is_file()), None)


def _path_key(path: Path) -> str:
    # Only the folders resolve: promotion moves a symlinked disc, not its target.
    return os.path.normcase(str(path.parent.resolve() / path.name)).casefold()


def listing_playlist(disc: Path) -> str | None:
    """The name of an .m3u beside a lone disc that lists it, which moving the
    disc would break, or None. Names match ignoring case, as Windows-authored
    playlists often differ in case from the files."""
    target = _path_key(disc)
    try:
        playlists = [
            entry
            for entry in disc.parent.iterdir()
            if entry.suffix.lower() == ".m3u" and entry.is_file()
        ]
    except OSError:
        return None
    for playlist in playlists:
        for candidates in _playlist_entries(playlist) or []:
            # The path an emulator would open, as first_playlist_entry picks it.
            on_disk = next((path for path in candidates if path.is_file()), None)
            named = [on_disk] if on_disk else candidates
            if any(_path_key(path) == target for path in named):
                return playlist.name
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
