from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import HTTPException

from handler.metadata.hasheous_handler import (
    HasheousHandler,
    extract_metadata_from_igdb_rom,
)

# The proxy keys expanded collections by id and returns `company` as a bare id,
# unlike IGDB's own list-of-objects shape.
PROXY_ROM = {
    "involved_companies": {
        "148214": {"id": 148214, "company": 70, "developer": True, "publisher": False},
        "225579": {"id": 225579, "company": 812, "developer": False, "publisher": True},
    },
}

IGDB_ROM = {
    "involved_companies": [
        {"company": {"name": "Retro Studios"}, "developer": True, "publisher": False},
        {"company": {"name": "Nintendo"}, "developer": False, "publisher": True},
    ],
}


def test_reads_the_proxys_dict_shaped_involvements():
    metadata = extract_metadata_from_igdb_rom(PROXY_ROM)

    assert metadata["companies"] == []
    assert metadata["publishers"] == []
    assert metadata["developers"] == []


def test_reads_igdbs_list_shaped_involvements():
    metadata = extract_metadata_from_igdb_rom(IGDB_ROM)

    assert metadata["publishers"] == ["Nintendo"]
    assert metadata["developers"] == ["Retro Studios"]


def test_involvements_are_optional():
    metadata = extract_metadata_from_igdb_rom({})

    assert metadata["publishers"] == []
    assert metadata["developers"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("POST", "https://hasheous.org/api"),
            response=httpx.Response(
                500, request=httpx.Request("POST", "https://hasheous.org/api")
            ),
        ),
        httpx.TimeoutException("too slow"),
    ],
    ids=["server_error", "timeout"],
)
async def test_request_propagates_an_unreachable_hasheous(failure: Exception):
    """A failed request has to stay distinguishable from a game Hasheous lacks."""
    handler = HasheousHandler()
    client = AsyncMock()
    client.request = AsyncMock(side_effect=failure)

    with (
        patch("handler.metadata.hasheous_handler.ctx_httpx_client") as ctx,
        pytest.raises(HTTPException),
    ):
        ctx.get.return_value = client
        await handler._request("https://hasheous.org/api")
