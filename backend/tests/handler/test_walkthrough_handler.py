from contextlib import asynccontextmanager

import httpx
import pytest

from handler.walkthrough_handler import (
    InvalidWalkthroughURLError,
    WalkthroughContentNotFound,
    WalkthroughFormat,
    WalkthroughSource,
    fetch_walkthrough,
    is_gamefaqs_url,
)
from utils.context import ctx_httpx_client


@asynccontextmanager
async def mock_http_client(responses: dict[str, str]):
    async def handler(request: httpx.Request) -> httpx.Response:
        body = responses.get(str(request.url))
        if body is None:
            return httpx.Response(status_code=404)
        return httpx.Response(status_code=200, text=body)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    token = ctx_httpx_client.set(client)
    try:
        yield
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


def test_url_matchers():
    assert is_gamefaqs_url(
        "https://gamefaqs.gamespot.com/snes/563504-secret-of-mana/faqs/55474"
    )
    assert not is_gamefaqs_url("https://example.com/guide")
    assert not is_gamefaqs_url(
        "https://steamcommunity.com/sharedfiles/filedetails/?id=3579263600"
    )


@pytest.mark.asyncio
async def test_fetch_gamefaqs_html_format():
    url = "https://gamefaqs.gamespot.com/snes/563504-secret-of-mana/faqs/55474"
    html = """
    <h2 class="title">Secret of Mana Walkthrough</h2>
    <div class="contrib1">Jane Doe</div>
    <div id='faqtext'><pre>First section</pre><pre>Second section</pre></div>
    """

    async with mock_http_client({url: html}):
        result = await fetch_walkthrough(url)

    assert result["source"] == WalkthroughSource.GAMEFAQS
    assert result["format"] == WalkthroughFormat.TEXT
    assert result["title"] == "Secret of Mana Walkthrough"
    assert result["author"] == "Jane Doe"
    assert "First section" in result["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/guide",
        "https://steamcommunity.com/sharedfiles/filedetails/?id=3579263600",
    ],
)
async def test_invalid_url_raises(url: str):
    with pytest.raises(InvalidWalkthroughURLError):
        await fetch_walkthrough(url)


@pytest.mark.asyncio
async def test_missing_content_raises():
    url = "https://gamefaqs.gamespot.com/snes/563504-secret-of-mana/faqs/55474"
    html = "<div id='faqtext'></div>"

    async with mock_http_client({url: html}):
        with pytest.raises(WalkthroughContentNotFound):
            await fetch_walkthrough(url)
