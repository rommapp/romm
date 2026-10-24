"""Finding a file in an ISO 9660 image through any random-access reader.

Only what locating a game's own files needs: it follows directory records from
the primary volume descriptor's root entry and ignores path tables, Joliet and
UDF, so a reader only fetches the few sectors on the way to the file.
"""

import struct
from typing import Protocol

ISO_SECTOR_SIZE = 2048
_PVD_SECTOR = 16  # ISO9660 primary volume descriptor lives at sector 16


class Iso9660Error(ValueError):
    """The image is not ISO 9660."""


class DiscReader(Protocol):
    def read_at(self, offset: int, length: int) -> bytes: ...


class Iso9660:
    def __init__(self, image: DiscReader) -> None:
        self._image = image
        pvd = image.read_at(_PVD_SECTOR * ISO_SECTOR_SIZE, ISO_SECTOR_SIZE)
        if len(pvd) < ISO_SECTOR_SIZE or pvd[0] != 1 or pvd[1:6] != b"CD001":
            raise Iso9660Error("not a valid ISO9660 image")

        root_record = pvd[156:190]
        self._root_lba = struct.unpack_from("<I", root_record, 2)[0]
        self._root_size = struct.unpack_from("<I", root_record, 10)[0]

    def find_file(self, path: str) -> tuple[int, int] | None:
        """Return ``(lba, size)`` for a file path, or ``None`` if not found."""
        components = [c for c in path.replace("\\", "/").split("/") if c]
        lba, size = self._root_lba, self._root_size
        for depth, component in enumerate(components):
            want_dir = depth < len(components) - 1
            located = self._find_in_dir(lba, size, component, want_dir)
            if located is None:
                return None
            lba, size = located
        return lba, size

    def read_file(self, path: str, max_bytes: int) -> bytes | None:
        """The file's first `max_bytes` bytes, or None if not found."""
        located = self.find_file(path)
        if located is None:
            return None
        lba, size = located
        return self._image.read_at(lba * ISO_SECTOR_SIZE, min(size, max_bytes))

    def _find_in_dir(
        self, dir_lba: int, dir_size: int, name: str, want_dir: bool
    ) -> tuple[int, int] | None:
        target = name.upper()
        data = self._image.read_at(dir_lba * ISO_SECTOR_SIZE, dir_size)
        # Directory records never cross a sector boundary; a zero length byte
        # means "skip to the next sector".
        for sector_start in range(0, len(data), ISO_SECTOR_SIZE):
            sector = data[sector_start : sector_start + ISO_SECTOR_SIZE]
            pos = 0
            while pos < len(sector):
                record_len = sector[pos]
                if record_len == 0:
                    break
                record = sector[pos : pos + record_len]
                pos += record_len
                if len(record) < 33:
                    break

                name_len = record[32]
                identifier = record[33 : 33 + name_len]
                # 0x00 / 0x01 are the "." and ".." self/parent entries.
                if name_len == 1 and identifier in (b"\x00", b"\x01"):
                    continue

                is_dir = bool(record[25] & 0x02)
                entry_name = identifier.split(b";", 1)[0].decode("ascii", "ignore")
                if entry_name.upper() == target and is_dir == want_dir:
                    lba = struct.unpack_from("<I", record, 2)[0]
                    size = struct.unpack_from("<I", record, 10)[0]
                    return lba, size
        return None
