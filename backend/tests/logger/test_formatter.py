import logging
import sys

import pytest
from fakeredis import FakeRedis

from handler import redis_handler
from logger.formatter import (
    RESET_ALL,
    YELLOW,
    Formatter,
    escape_control_chars,
    highlight,
)
from logger.log_stream_handler import LOG_BUFFER_KEY, LogStreamHandler
from utils import json_module


def _record(msg: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="romm",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args or None,
        exc_info=None,
    )


@pytest.mark.parametrize(
    ("raw", "escaped"),
    [
        ("a\nb", "a\\nb"),
        ("a\r\nINFO: forged", "a\\r\\nINFO: forged"),
        ("bell\x07 and nul\x00", "bell and nul"),
        ("clear\x1b[2J screen", "clear[2J screen"),
        ("title\x1b]0;pwned\x07", "title]0;pwned"),
        ("csi\x9b2J", "csi2J"),
        ("tab\tkept", "tab\tkept"),
        (f"{YELLOW}colour{RESET_ALL}", f"{YELLOW}colour{RESET_ALL}"),
    ],
)
def test_escape_control_chars(raw: str, escaped: str) -> None:
    assert escape_control_chars(raw) == escaped


def test_message_line_breaks_are_escaped() -> None:
    output = Formatter().format(_record("search for %s", "x\nINFO: forged"))

    assert "\n" not in output
    assert "search for x\\nINFO: forged" in output


def test_highlight_colours_survive() -> None:
    output = Formatter().format(_record(f"Scanning {highlight('Game\nTitle')}"))

    assert f"{YELLOW}Game\\nTitle{RESET_ALL}" in output


def test_traceback_stays_multiline() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record("failed\nagain")
        record.exc_info = sys.exc_info()

    output = Formatter().format(record)

    first_line, traceback = output.split("\n", 1)
    assert first_line.endswith("failed\\nagain")
    assert traceback.startswith("Traceback (most recent call last):")
    assert traceback.rstrip().endswith("ValueError: boom")


def test_formatting_leaves_the_record_untouched() -> None:
    record = _record("a\n%s", "b")

    Formatter().format(record)

    assert record.getMessage() == "a\nb"


def test_log_buffer_gets_the_escaped_message(mocker) -> None:
    redis = FakeRedis(version=7)
    mocker.patch.object(redis_handler, "redis_client", redis)

    LogStreamHandler().emit(_record("user %s", "x\r\nERROR: forged\x1b[2J"))

    (payload,) = redis.lrange(LOG_BUFFER_KEY, 0, -1)
    assert json_module.loads(payload)["message"] == "user x\\r\\nERROR: forged[2J"
