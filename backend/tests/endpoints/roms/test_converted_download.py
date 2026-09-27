import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import unquote

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from config import ROM_CONVERTO_CACHE_PATH
from models.rom import Rom

CONVERTED = Path(ROM_CONVERTO_CACHE_PATH) / "1-abc" / "test_rom.chd"


@pytest.fixture
def conversion(mocker):
    """Enable download conversion for the test platform with every step mocked."""
    mocker.patch(
        "endpoints.roms.cm.get_config",
        return_value=SimpleNamespace(
            CONVERTO=SimpleNamespace(
                download_conversion_enabled=True,
                platform_formats={"test_platform_slug": "chd"},
            )
        ),
    )
    mocker.patch(
        "endpoints.roms.rom_converto_service.is_enabled",
        AsyncMock(return_value=True),
    )
    return SimpleNamespace(
        cached=mocker.patch("endpoints.roms.get_cached_converted", return_value=None),
        convert=mocker.patch(
            "endpoints.roms.get_or_convert", AsyncMock(return_value=CONVERTED)
        ),
    )


def _redirect(response) -> str:
    return unquote(response.headers["X-Accel-Redirect"])


def test_download_is_untouched_without_the_opt_in(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.cached.assert_not_called()
    conversion.convert.assert_not_called()


def test_opt_in_serves_the_converted_copy(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    assert "test_rom.chd" in response.headers["Content-Disposition"]
    conversion.convert.assert_awaited_once()


def test_opt_in_serves_a_prewarmed_copy_over_the_sync_cap(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch("endpoints.roms.ROM_CONVERTO_MAX_SYNC_SIZE_MB", 0)
    conversion.cached.return_value = CONVERTED

    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    assert conversion.cached.call_args.kwargs == {"touch": True}
    conversion.convert.assert_not_called()


def test_opt_in_over_the_sync_cap_serves_the_original(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch("endpoints.roms.ROM_CONVERTO_MAX_SYNC_SIZE_MB", 0)

    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.convert.assert_not_called()


def test_opt_in_past_the_deadline_serves_the_original(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch("endpoints.roms.SYNC_CONVERSION_DEADLINE_SECONDS", 0.01)

    async def slow_convert(*args, **kwargs):
        await asyncio.sleep(0.2)
        return CONVERTED

    conversion.convert.side_effect = slow_convert

    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.convert.assert_called_once()


def test_head_reports_a_cached_copy_but_never_converts(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"/api/roms/{rom.id}/content/test_rom.zip"

    uncached = client.head(url, headers=headers, params={"converted": "true"})
    conversion.cached.return_value = CONVERTED
    cached = client.head(url, headers=headers, params={"converted": "true"})

    assert _redirect(uncached) == f"/library/{rom_file.full_path}"
    assert _redirect(cached) == "/cache/converts/1-abc/test_rom.chd"
    assert conversion.cached.call_args.kwargs == {"touch": False}
    conversion.convert.assert_not_called()
