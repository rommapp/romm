from collections.abc import AsyncIterator, Awaitable, Callable

import httpx2
import pytest

from handler.metadata.image_proxy import (
    PROVIDER_IMAGE_MAX_BYTES,
    fetch_provider_image,
    is_provider_image_url,
)
from utils.context import ctx_httpx_client


@pytest.mark.parametrize(
    "url",
    [
        "https://images.igdb.com/igdb/image/upload/t_cover_big/co1.jpg",
        "https://cdn2.steamgriddb.com/grid/abc.png",
        "https://images.launchbox-app.com/cover.png",
        "https://neoclone.screenscraper.fr/api2/mediaJeu.php?devid=x&media=box-2D",
        "https://cdn.mobygames.com/covers/1.webp",
        "https://thumbnails.libretro.com/Sega%20-%20Mega%20Drive/Named_Boxarts/S.png",
        "https://infinity.unstable.life/images/Logos/00/00/0000?type=jpg",
        "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1/x.jpg",
        "https://IMAGES.IGDB.COM/a.jpg",
        "https://images.igdb.com:443/a.jpg",
    ],
)
def test_provider_image_hosts_are_allowed(url: str):
    assert is_provider_image_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://images.igdb.com/a.jpg",
        "https://igdb.com.evil.example/a.jpg",
        "https://notigdb.com/a.jpg",
        "https://evil.example/images.igdb.com/a.jpg",
        "https://libretro.com/a.png",
        "https://user:pw@images.igdb.com/a.jpg",
        "https://images.igdb.com:8443/a.jpg",
        "https://127.0.0.1/a.jpg",
        "https://localhost/a.jpg",
        "file:///etc/passwd",
        "https://[::1/a.jpg",
        "",
    ],
)
def test_other_urls_are_rejected(url: str):
    assert not is_provider_image_url(url)


async def _fetch_with(
    respond: Callable[[httpx2.Request], Awaitable[httpx2.Response]],
    url: str = "https://images.igdb.com/a.jpg",
):
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
    token = ctx_httpx_client.set(client)
    try:
        return await fetch_provider_image(url)
    finally:
        ctx_httpx_client.reset(token)
        await client.aclose()


async def test_fetch_returns_the_image_and_its_type():
    async def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, content=b"jpeg-bytes", headers={"content-type": "image/jpeg"}
        )

    image = await _fetch_with(respond)

    assert image is not None
    assert image.content == b"jpeg-bytes"
    assert image.media_type == "image/jpeg"


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(404, content=b"", headers={"content-type": "image/png"}),
        httpx2.Response(200, content=b"<html>", headers={"content-type": "text/html"}),
        httpx2.Response(
            200, content=b"<svg/>", headers={"content-type": "image/svg+xml"}
        ),
        httpx2.Response(
            302,
            headers={"location": "http://127.0.0.1/", "content-type": "image/png"},
        ),
    ],
)
async def test_fetch_rejects_errors_redirects_and_non_raster_content(
    response: httpx2.Response,
):
    async def respond(request: httpx2.Request) -> httpx2.Response:
        return response

    assert await _fetch_with(respond) is None


async def test_fetch_stops_past_the_size_cap():
    chunk = b"x" * (1024 * 1024)

    async def endless() -> AsyncIterator[bytes]:
        while True:
            yield chunk

    async def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, content=endless(), headers={"content-type": "image/png"}
        )

    assert await _fetch_with(respond) is None


async def test_fetch_rejects_a_declared_oversize_body():
    async def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b"x",
            headers={
                "content-type": "image/png",
                "content-length": str(PROVIDER_IMAGE_MAX_BYTES + 1),
            },
        )

    assert await _fetch_with(respond) is None


async def test_fetch_swallows_transport_errors():
    async def respond(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectTimeout("timed out", request=request)

    assert await _fetch_with(respond) is None
