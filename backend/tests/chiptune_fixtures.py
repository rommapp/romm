"""Header-only console sound files libgme can list songs from."""


def _field(text: str) -> bytes:
    return text.encode("latin-1").ljust(32, b"\0")


def nsf_bytes(
    songs: int,
    title: str = "Mega Game",
    artist: str = "Composer",
    copyright: str = "1990 Maker",
) -> bytes:
    """An NSF holding the given number of songs."""
    header = bytearray(0x80)
    header[0:5] = b"NESM\x1a"
    header[5] = 1
    header[6] = songs
    header[7] = 1
    header[8:14] = bytes([0x00, 0x80, 0x00, 0x80, 0x00, 0x80])
    header[0x0E:0x2E] = _field(title)
    header[0x2E:0x4E] = _field(artist)
    header[0x4E:0x6E] = _field(copyright)
    header[0x6E:0x70] = (16639).to_bytes(2, "little")
    return bytes(header) + b"\x60" * 16


def hes_bytes() -> bytes:
    """A HES, a format that doesn't record its song count."""
    return b"HESM".ljust(0x40, b"\0") + b"\0" * 0x90
