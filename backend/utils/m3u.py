from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.rom import RomFile


def generate_m3u_content(
    files: list[RomFile],
    hidden_folder: bool,
) -> bytes:
    """Generate M3U playlist content for multi-file ROMs.

    If .cue files are present, only those are listed (avoids invalid entries
    like raw .bin tracks). Otherwise all files are listed.
    """
    cue_files = [f for f in files if f.file_extension.lower() == "cue"]
    m3u_files = cue_files if cue_files else files
    return "\n".join(
        f.file_name_for_download(hidden_folder) for f in m3u_files
    ).encode()
