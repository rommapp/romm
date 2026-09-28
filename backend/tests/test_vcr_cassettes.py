from pathlib import Path
from typing import Any

import pytest

CASSETTES = sorted(Path(__file__).parent.glob("**/cassettes/**/*.yaml"))


def _scrub(vcr_config: dict[str, Any], body: bytes) -> bytes:
    response = vcr_config["before_record_response"]({"body": {"string": body}})
    return response["body"]["string"]


def test_response_body_credentials_are_masked(vcr_config):
    body = _scrub(
        vcr_config,
        b'"url": "https://ss.fr/img.png?devid=dev1&devpassword=s3cret'
        b'&output=json&ssid=user1&sspassword=hunter2"',
    )

    for secret in (b"dev1", b"s3cret", b"user1", b"hunter2"):
        assert secret not in body
    assert b"output=json" in body


def test_short_keys_do_not_match_inside_longer_names(vcr_config):
    body = b"https://example.com/?display=grid&key=1"

    assert _scrub(vcr_config, body) == body


@pytest.mark.parametrize("cassette", CASSETTES, ids=lambda p: p.name)
def test_cassette_holds_no_credentials(vcr_config, cassette: Path):
    raw = cassette.read_bytes()

    assert _scrub(vcr_config, raw) == raw
