"""Bytes that end like a zip without being one, as an emulator state can."""

import io
import zipfile

from tests._zipfile_shim import reload_zipfile

# The tail of an archive after a longer lead, the tail after a shorter lead, and
# a whole archive after a lead of its own.
EMBEDDINGS = ["tail-state-longer", "tail-archive-longer", "whole-archive"]


def game_archive() -> bytes:
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("game.bin", bytes(range(256)) * 64)
        zf.writestr("game.cfg", b"region=jp\n" * 16)
        zf.comment = b"TORRENTZIPPED-00000000"
    return buffer.getvalue()


def embedded_archive(embedding: str) -> bytes:
    """State-like bytes holding `game_archive()` the way `embedding` names."""
    archive = game_archive()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        start_dir = zf.start_dir
    tail = archive[start_dir:]
    if embedding == "tail-state-longer":
        body = b"\x00" * (start_dir + 4096) + tail
    elif embedding == "tail-archive-longer":
        body = b"\x00" * (start_dir // 2) + tail
    else:
        body = b"\x00" * 4096 + archive
    return body + b"\xff" * 120
