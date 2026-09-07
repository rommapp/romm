import httpx
import pytest

from handler.walkthrough import (
    fetch_gamefaqs_guide,
    parse_gamefaqs_guide,
    validate_gamefaqs_url,
)
from handler.walkthrough.gamefaqs import (
    MAX_GUIDE_BYTES,
    GameFAQsFetchError,
    is_bot_challenge,
)
from utils.context import ctx_httpx_client


def test_parse_extracts_title_author_and_pre_text():
    html = (
        "<html><head>"
        "<title>Chrono Trigger - FAQ/Walkthrough - GameFAQs</title>"
        '<meta name="author" content="John Doe">'
        '<meta property="og:title" content="Chrono Trigger FAQ">'
        "</head><body>"
        '<div id="faqtext"><pre>Line 1\nLine 2 &amp; more</pre></div>'
        "</body></html>"
    )
    guide = parse_gamefaqs_guide(html)
    assert guide["title"] == "Chrono Trigger FAQ"
    assert guide["author"] == "John Doe"
    assert guide["text"] == "Line 1\nLine 2 & more"


def test_parse_falls_back_to_title_tag_and_strips_suffix():
    html = (
        "<html><head><title>Some Guide - GameFAQs</title></head>"
        "<body><pre>body</pre></body></html>"
    )
    guide = parse_gamefaqs_guide(html)
    assert guide["title"] == "Some Guide"
    assert guide["text"] == "body"


def test_parse_no_guide_text_returns_empty():
    guide = parse_gamefaqs_guide("<html><body><p>nothing here</p></body></html>")
    assert guide["text"] == ""


@pytest.mark.parametrize(
    "url",
    [
        "http://gamefaqs.gamespot.com/x",  # not https
        "https://evil.example.com/x",  # wrong host
        "ftp://gamefaqs.com/x",  # wrong scheme
        "https://notgamefaqs.com/x",  # lookalike host
    ],
)
def test_validate_rejects_bad_urls(url):
    with pytest.raises(ValueError):
        validate_gamefaqs_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://gamefaqs.gamespot.com/snes/563538-chrono-trigger/faqs/1",
        "https://www.gamefaqs.com/snes/563538/faqs/1",
        "https://gamefaqs.com/snes/563538/faqs/1",
    ],
)
def test_validate_accepts_gamefaqs_urls(url):
    assert validate_gamefaqs_url(url) == url


def _response(
    status: int, headers: dict[str, str], content: bytes = b""
) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers=headers,
        content=content,
        # raise_for_status() needs the originating request attached.
        request=httpx.Request("GET", "https://gamefaqs.gamespot.com/x"),
    )


class _StreamingClient:
    """Minimal stand-in for the shared httpx client's streaming interface."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def build_request(self, *_args, **_kwargs):
        return None

    async def send(self, *_args, **_kwargs):
        return self._response


def test_detects_cloudflare_managed_challenge():
    # Headers as served by GameFAQs behind Cloudflare bot protection.
    response = _response(403, {"cf-mitigated": "challenge", "server": "cloudflare"})
    assert is_bot_challenge(response)


@pytest.mark.parametrize("status", [403, 503])
def test_detects_cloudflare_refusal_without_mitigation_header(status):
    assert is_bot_challenge(_response(status, {"server": "cloudflare"}))


@pytest.mark.parametrize(
    ("status", "headers"),
    [
        (200, {"cf-mitigated": "challenge", "server": "cloudflare"}),  # served
        (403, {"server": "nginx"}),  # a real permission denial
        (404, {"server": "cloudflare"}),  # guide is gone, not blocked
        (500, {}),  # upstream fault
    ],
)
def test_other_responses_are_not_treated_as_challenges(status, headers):
    assert not is_bot_challenge(_response(status, headers))


async def test_fetch_stops_reading_at_the_size_cap():
    """The cap must bound what is read, not truncate an already-buffered body."""
    oversized = b"<pre>" + b"x" * (MAX_GUIDE_BYTES * 2)
    served = _response(200, {"content-type": "text/html"}, content=oversized)

    token = ctx_httpx_client.set(_StreamingClient(served))  # type: ignore[arg-type]
    try:
        guide = await fetch_gamefaqs_guide(
            "https://gamefaqs.gamespot.com/snes/563538-chrono-trigger/faqs/1"
        )
    finally:
        ctx_httpx_client.reset(token)

    # Body is capped, and the guide still parses out of the truncated HTML.
    assert 0 < len(guide["text"]) <= MAX_GUIDE_BYTES


async def test_fetch_explains_how_to_recover_from_a_bot_challenge():
    """A challenge must surface as actionable advice, not an opaque 403."""
    challenge = _response(403, {"cf-mitigated": "challenge", "server": "cloudflare"})

    token = ctx_httpx_client.set(_StreamingClient(challenge))  # type: ignore[arg-type]
    try:
        with pytest.raises(GameFAQsFetchError) as exc:
            await fetch_gamefaqs_guide(
                "https://gamefaqs.gamespot.com/gba/471043-advance-wars/faqs/23604"
            )
    finally:
        ctx_httpx_client.reset(token)

    assert "blocking automated requests" in str(exc.value)
    assert "upload" in str(exc.value)
