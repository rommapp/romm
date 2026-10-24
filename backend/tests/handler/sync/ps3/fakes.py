"""An in-memory PS3 behind `AsyncPS3Ftp`'s interface, and the files it holds."""

import ftplib
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TypeVar

from tests.handler.sync.retroarch.test_psp import _build_fake_sfo
from tests.utils.test_psp_hasher import ISO_SECTOR_SIZE, _dir_record, _extent

from handler.sync.ps3.ftp import AsyncPS3Ftp, FtpEntry, FtpFileTooLarge, PS3Ftp

SAVEDATA = "/dev_hdd0/home/00000001/savedata"
WRITTEN_AT = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def build_sfo(**fields: str) -> bytes:
    return _build_fake_sfo(dict(fields))


def build_ps3_iso(param_sfo: bytes) -> bytes:
    """A tiny ISO 9660 image holding PS3_GAME/PARAM.SFO."""
    root, game, sfo = 18, 19, 20
    iso = bytearray((sfo + 1) * ISO_SECTOR_SIZE)
    pvd = bytearray(ISO_SECTOR_SIZE)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[156:190] = _dir_record(b"\x00", root, ISO_SECTOR_SIZE, True)
    iso[16 * ISO_SECTOR_SIZE : 17 * ISO_SECTOR_SIZE] = pvd
    iso[root * ISO_SECTOR_SIZE : (root + 1) * ISO_SECTOR_SIZE] = _extent(
        [
            _dir_record(b"\x00", root, ISO_SECTOR_SIZE, True),
            _dir_record(b"\x01", root, ISO_SECTOR_SIZE, True),
            _dir_record(b"PS3_GAME", game, ISO_SECTOR_SIZE, True),
        ]
    )
    iso[game * ISO_SECTOR_SIZE : (game + 1) * ISO_SECTOR_SIZE] = _extent(
        [
            _dir_record(b"\x00", game, ISO_SECTOR_SIZE, True),
            _dir_record(b"\x01", root, ISO_SECTOR_SIZE, True),
            _dir_record(b"PARAM.SFO;1", sfo, len(param_sfo), False),
        ]
    )
    iso[sfo * ISO_SECTOR_SIZE : sfo * ISO_SECTOR_SIZE + len(param_sfo)] = param_sfo
    return bytes(iso)


T = TypeVar("T")


class _BlockingSession(PS3Ftp):
    """The blocking session `FakeConsole.run` hands out, over the same files."""

    def __init__(self, console: "FakeConsole") -> None:
        self._console = console

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        self._console.reads.append(path)
        return self._console.files[path][0][offset : offset + length]


class FakeConsole(AsyncPS3Ftp):
    """A console filesystem behind the session the code under test receives."""

    def __init__(self) -> None:
        self.files: dict[str, tuple[bytes, datetime]] = {}
        self.dirs: set[str] = {"/"}
        self.reads: list[str] = []
        self.writes: list[str] = []
        # What a test does when the code reads or writes a path, as a game saving.
        self.on_read: Callable[[str], None] | None = None
        self.on_write: Callable[[str], None] | None = None
        # Sizes listed instead of the real ones, as a hostile server would.
        self.listed_sizes: dict[str, int] = {}

    def add_dir(self, path: str) -> None:
        while path not in self.dirs:
            self.dirs.add(path)
            path = path.rsplit("/", 1)[0] or "/"

    def add_file(self, path: str, data: bytes, modified: datetime = WRITTEN_AT) -> None:
        self.add_dir(path.rsplit("/", 1)[0])
        self.files[path] = (data, modified)

    def add_save(
        self, folder: str, files: dict[str, bytes], modified: datetime = WRITTEN_AT
    ) -> None:
        for name, data in files.items():
            self.add_file(f"{SAVEDATA}/{folder}/{name}", data, modified)

    def folder(self, path: str) -> dict[str, bytes]:
        prefix = f"{path}/"
        return {
            p.removeprefix(prefix): data
            for p, (data, _) in self.files.items()
            if p.startswith(prefix) and "/" not in p.removeprefix(prefix)
        }

    def _children(self, path: str) -> list[str]:
        prefix = path.rstrip("/") + "/"
        names = {
            p.removeprefix(prefix).split("/", 1)[0]
            for p in [*self.dirs, *self.files]
            if p.startswith(prefix) and p != prefix
        }
        return sorted(names)

    async def list(self, path: str) -> list[FtpEntry]:
        if path not in self.dirs:
            raise ftplib.error_perm(f"550 {path} not found")
        entries = []
        for name in self._children(path):
            child = f"{path.rstrip('/')}/{name}"
            if child in self.files:
                data, modified = self.files[child]
                size = self.listed_sizes.get(child, len(data))
                entries.append(FtpEntry(name, False, size, modified))
            else:
                entries.append(FtpEntry(name, True, 0, WRITTEN_AT))
        return entries

    async def exists(self, path: str) -> bool:
        return path in self.dirs or path in self.files

    async def read(self, path: str, max_bytes: int) -> bytes:
        self.reads.append(path)
        if path not in self.files:
            raise ftplib.error_perm(f"550 {path} not found")
        data = self.files[path][0]
        if self.on_read:
            self.on_read(path)
        if len(data) > max_bytes:
            raise FtpFileTooLarge(path)
        return data

    async def run(self, func: Callable[[PS3Ftp], T]) -> T:
        return func(_BlockingSession(self))

    async def write(self, path: str, data: bytes) -> None:
        if path.rsplit("/", 1)[0] not in self.dirs:
            raise ftplib.error_perm(f"550 no folder for {path}")
        self.writes.append(path)
        self.files[path] = (data, datetime.now(timezone.utc))
        if self.on_write:
            self.on_write(path)

    async def mkdir(self, path: str) -> None:
        self.dirs.add(path)

    async def rename(self, source: str, target: str) -> None:
        for paths in (self.dirs, self.files):
            for path in [p for p in paths if p == source or p.startswith(f"{source}/")]:
                moved = target + path.removeprefix(source)
                if isinstance(paths, set):
                    paths.discard(path)
                    paths.add(moved)
                else:
                    paths[moved] = paths.pop(path)

    async def remove_tree(self, path: str) -> None:
        self.dirs = {p for p in self.dirs if p != path and not p.startswith(f"{path}/")}
        self.files = {
            p: v for p, v in self.files.items() if not p.startswith(f"{path}/")
        }

    async def close(self) -> None:
        pass
