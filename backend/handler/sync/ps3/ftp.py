"""FTP access to a PS3 running a homebrew FTP server, such as webMAN MOD's."""

from __future__ import annotations

import asyncio

# The PS3 serves its files over plain FTP only, and only on the LAN.
import ftplib  # nosec B402
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Final, TypeVar

FTP_TIMEOUT_SECONDS = 15
PROBE_TIMEOUT_SECONDS = 3

# webMAN sends names as raw bytes; latin-1 round-trips any of them unchanged.
_WIRE_ENCODING = "latin-1"
_CHUNK_BYTES = 64 * 1024

T = TypeVar("T")

# Socket errors and EOF included, as a dropped connection raises either.
FTP_ERRORS: Final[tuple[type[Exception], ...]] = ftplib.all_errors


class FtpFileTooLarge(Exception):
    """A download passed the byte limit its caller set."""


@dataclass(frozen=True)
class FtpEntry:
    """One entry of a directory listing, named as the server spells it."""

    name: str
    is_dir: bool
    size: int
    modified: datetime | None

    @property
    def display_name(self) -> str:
        """The name decoded as the UTF-8 the console writes."""
        return self.name.encode(_WIRE_ENCODING).decode("utf-8", errors="replace")


def _parse_modify(value: str | None) -> datetime | None:
    """An MLSD `modify` fact (``YYYYMMDDHHMMSS[.fff]``), which RFC 3659 puts in UTC."""
    if not value:
        return None
    try:
        return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _parse_size(facts: dict[str, str]) -> int:
    try:
        return int(facts.get("size") or facts.get("sizd") or 0)
    except ValueError:
        return 0


class PS3Ftp:
    """A blocking FTP session; `AsyncPS3Ftp` runs it off the event loop."""

    def __init__(self, ftp: ftplib.FTP) -> None:
        self._ftp = ftp

    @classmethod
    def connect(cls, host: str, port: int) -> PS3Ftp:
        ftp = ftplib.FTP(
            encoding=_WIRE_ENCODING, timeout=FTP_TIMEOUT_SECONDS
        )  # nosec B321
        try:
            ftp.connect(host, port)
            # webMAN accepts any login, and anonymous is what other clients send.
            ftp.login()
            ftp.voidcmd("TYPE I")
        except BaseException:
            ftp.close()
            raise
        return cls(ftp)

    def close(self) -> None:
        try:
            self._ftp.quit()
        except ftplib.all_errors:
            self._ftp.close()

    def list(self, path: str) -> list[FtpEntry]:
        entries = []
        for name, facts in self._ftp.mlsd(path, ["type", "size", "sizd", "modify"]):
            kind = facts.get("type", "").lower()
            if kind in ("cdir", "pdir") or name in (".", ".."):
                continue
            entries.append(
                FtpEntry(
                    name=name,
                    is_dir=kind == "dir",
                    size=_parse_size(facts),
                    modified=_parse_modify(facts.get("modify")),
                )
            )
        return entries

    def exists(self, path: str) -> bool:
        parent, _, name = path.rstrip("/").rpartition("/")
        try:
            return any(entry.name == name for entry in self.list(parent or "/"))
        except ftplib.error_perm:
            return False

    def read(self, path: str, max_bytes: int) -> bytes:
        """The whole file, which must not exceed `max_bytes`.

        Raises:
            FtpFileTooLarge: The file is larger than `max_bytes`.
        """
        buffer = BytesIO()

        def _collect(chunk: bytes) -> None:
            if buffer.tell() + len(chunk) > max_bytes:
                raise FtpFileTooLarge(path)
            buffer.write(chunk)

        try:
            self._ftp.retrbinary(f"RETR {path}", _collect, blocksize=_CHUNK_BYTES)
        except FtpFileTooLarge:
            self._abort_transfer()
            raise
        return buffer.getvalue()

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        """`length` bytes from `offset`, fewer when the file ends first."""
        conn = self._ftp.transfercmd(f"RETR {path}", rest=offset)
        buffer = bytearray()
        try:
            while len(buffer) < length:
                chunk = conn.recv(min(_CHUNK_BYTES, length - len(buffer)))
                if not chunk:
                    break
                buffer += chunk
        finally:
            conn.close()
        # Closing early aborts the transfer, and servers answer that with an error.
        try:
            self._ftp.voidresp()
        except ftplib.all_errors:
            pass
        return bytes(buffer)

    def write(self, path: str, data: bytes) -> None:
        self._ftp.storbinary(f"STOR {path}", BytesIO(data), blocksize=_CHUNK_BYTES)

    def mkdir(self, path: str) -> None:
        self._ftp.mkd(path)

    def rename(self, source: str, target: str) -> None:
        self._ftp.rename(source, target)

    def remove_tree(self, path: str) -> None:
        for entry in self.list(path):
            child = f"{path}/{entry.name}"
            if entry.is_dir:
                self.remove_tree(child)
            else:
                self._ftp.delete(child)
        self._ftp.rmd(path)

    def _abort_transfer(self) -> None:
        try:
            self._ftp.abort()
        except ftplib.all_errors:
            pass


class FtpFileReader:
    """Random access to one file on the server, for `utils.iso9660.Iso9660`."""

    def __init__(self, ftp: PS3Ftp, path: str) -> None:
        self._ftp = ftp
        self._path = path

    def read_at(self, offset: int, length: int) -> bytes:
        return self._ftp.read_range(self._path, offset, length)


class AsyncPS3Ftp:
    """`PS3Ftp` with each call in a worker thread, one call at a time."""

    def __init__(self, ftp: PS3Ftp) -> None:
        self._ftp = ftp
        self._lock = asyncio.Lock()

    @classmethod
    async def connect(cls, host: str, port: int) -> AsyncPS3Ftp:
        return cls(await asyncio.to_thread(PS3Ftp.connect, host, port))

    async def _run(self, func: Callable[[], T]) -> T:
        async with self._lock:
            return await asyncio.to_thread(func)

    async def run(self, func: Callable[[PS3Ftp], T]) -> T:
        """`func` given the blocking session, for work spanning several calls."""
        return await self._run(lambda: func(self._ftp))

    async def close(self) -> None:
        await self._run(self._ftp.close)

    async def list(self, path: str) -> list[FtpEntry]:
        return await self._run(lambda: self._ftp.list(path))

    async def exists(self, path: str) -> bool:
        return await self._run(lambda: self._ftp.exists(path))

    async def read(self, path: str, max_bytes: int) -> bytes:
        return await self._run(lambda: self._ftp.read(path, max_bytes))

    async def write(self, path: str, data: bytes) -> None:
        await self._run(lambda: self._ftp.write(path, data))

    async def mkdir(self, path: str) -> None:
        await self._run(lambda: self._ftp.mkdir(path))

    async def rename(self, source: str, target: str) -> None:
        await self._run(lambda: self._ftp.rename(source, target))

    async def remove_tree(self, path: str) -> None:
        await self._run(lambda: self._ftp.remove_tree(path))


async def probe(host: str, port: int) -> str | None:
    """The FTP server's greeting, or None when nothing answers in time."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), PROBE_TIMEOUT_SECONDS
        )
    except OSError, TimeoutError:
        return None
    try:
        line = await asyncio.wait_for(reader.readline(), PROBE_TIMEOUT_SECONDS)
    except OSError, TimeoutError:
        line = b""
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
    # Reachable but silent is still reachable, so that answers with "".
    return line.decode(_WIRE_ENCODING).strip().removeprefix("220").strip()
