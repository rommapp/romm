import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from handler.sync.ps3.ftp import FtpEntry, FtpFileTooLarge, PS3Ftp, probe


class TestPS3Ftp:
    def test_lists_entries_from_mlsd(self):
        ftp = MagicMock()
        ftp.mlsd.return_value = iter(
            [
                (".", {"type": "cdir"}),
                ("..", {"type": "pdir"}),
                (
                    "PARAM.SFO",
                    {"type": "file", "size": "2736", "modify": "20261011131218"},
                ),
                ("SUB", {"type": "dir", "sizd": "512", "modify": "garbage"}),
            ]
        )

        entries = PS3Ftp(ftp).list("/dev_hdd0")

        assert entries == [
            FtpEntry(
                "PARAM.SFO",
                False,
                2736,
                datetime(2026, 10, 11, 13, 12, 18, tzinfo=timezone.utc),
            ),
            FtpEntry("SUB", True, 512, None),
        ]

    def test_read_stops_past_the_limit(self):
        ftp = MagicMock()
        ftp.retrbinary.side_effect = lambda _cmd, callback, blocksize: callback(
            b"x" * 11
        )

        with pytest.raises(FtpFileTooLarge):
            PS3Ftp(ftp).read("/big", max_bytes=10)
        ftp.abort.assert_called_once()

    def test_display_name_decodes_utf8_sent_as_raw_bytes(self):
        wire = "Jak™".encode().decode("latin-1")
        assert FtpEntry(wire, False, 0, None).display_name == "Jak™"


@pytest.fixture
async def server() -> AsyncIterator[int]:
    async def greet(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        writer.write(b"220 webMANftpd 1.47.48n MOD\r\n")
        await writer.drain()
        writer.close()

    srv = await asyncio.start_server(greet, "127.0.0.1", 0)
    yield srv.sockets[0].getsockname()[1]
    srv.close()
    await srv.wait_closed()


class TestProbe:
    async def test_returns_the_greeting(self, server: int):
        assert await probe("127.0.0.1", server) == "webMANftpd 1.47.48n MOD"

    async def test_none_when_nothing_listens(self):
        srv = await asyncio.start_server(lambda *_: None, "127.0.0.1", 0)
        port = srv.sockets[0].getsockname()[1]
        srv.close()
        await srv.wait_closed()

        assert await probe("127.0.0.1", port) is None
