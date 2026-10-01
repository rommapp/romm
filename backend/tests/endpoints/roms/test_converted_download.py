import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import unquote

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from adapters.services.rom_converto import resolve_operation
from config import ROM_CONVERTO_CACHE_PATH
from config.config_manager import ConvertoConfig
from models.rom import Rom
from utils import conversion_cache
from utils.conversion_cache import get_cached_converted

CONVERTED = Path(ROM_CONVERTO_CACHE_PATH) / "1-abc" / "test_rom.chd"


@pytest.fixture
def conversion(mocker):
    """Enable download conversion for the test platform with every step mocked."""
    converto = ConvertoConfig(
        download_conversion_enabled=True,
        platform_formats={"test_platform_slug": "chd"},
    )
    mocker.patch(
        "utils.conversion_cache.cm.get_config",
        return_value=SimpleNamespace(CONVERTO=converto),
    )
    mocker.patch(
        "utils.conversion_cache.rom_converto_service.is_enabled",
        AsyncMock(return_value=True),
    )
    return SimpleNamespace(
        converto=converto,
        cached=mocker.patch(
            "utils.conversion_cache.get_cached_converted", return_value=None
        ),
        convert=mocker.patch(
            "utils.conversion_cache.get_or_convert", AsyncMock(return_value=CONVERTED)
        ),
    )


@pytest.fixture
def cached_copy(tmp_path: Path, conversion, mocker) -> Path:
    final = tmp_path / "cache/converts/1-abc/test_rom.chd"
    final.parent.mkdir(parents=True)
    final.write_bytes(b"x" * 120)
    served = time.time() - 3600
    os.utime(final, (served, served))
    resolved = resolve_operation("psp", "chd", "test_rom.iso")
    assert resolved is not None
    mocker.patch.object(conversion_cache, "ROMM_BASE_PATH", str(tmp_path))
    mocker.patch.object(
        conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(final.parent.parent)
    )
    mocker.patch.object(conversion_cache, "_lookup", return_value=(resolved[0], final))
    conversion.cached.side_effect = get_cached_converted
    return final


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


def test_opt_in_serves_a_cached_copy_over_the_sync_cap(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    conversion.converto.max_sync_size_mb = 0
    conversion.cached.return_value = CONVERTED

    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    conversion.convert.assert_not_called()


def test_opt_in_over_the_sync_cap_converts_in_the_background(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    conversion.converto.max_sync_size_mb = 0

    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.convert.assert_called_once()


def test_opt_in_past_the_deadline_serves_the_original(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch("utils.conversion_cache.SYNC_CONVERSION_DEADLINE_SECONDS", 0.01)

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
    conversion.convert.assert_not_called()


def test_a_kiosk_visitor_never_starts_a_conversion(
    client: TestClient, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch("handler.auth.hybrid_auth.KIOSK_MODE", True)
    mocker.patch("handler.auth.permissions.KIOSK_MODE", True)

    response = client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.convert.assert_not_called()


@pytest.mark.parametrize(
    ("method", "visitor"),
    [
        pytest.param("get", "authenticated", id="authenticated-download"),
        pytest.param("get", "kiosk", id="kiosk-download"),
        pytest.param("get", "public", id="download-auth-disabled"),
        pytest.param("head", "authenticated", id="metadata"),
    ],
)
def test_get_refreshes_a_cached_copy_but_head_does_not(
    client: TestClient,
    access_token: str,
    rom: Rom,
    rom_file,
    conversion,
    cached_copy: Path,
    mocker,
    method,
    visitor,
):
    headers = {"Authorization": f"Bearer {access_token}"}
    if visitor == "kiosk":
        mocker.patch("handler.auth.hybrid_auth.KIOSK_MODE", True)
        mocker.patch("handler.auth.permissions.KIOSK_MODE", True)
        headers = {}
    elif visitor == "public":
        # Download scopes are fixed when the route decorators are evaluated.
        mocker.patch("decorators.auth.has_required_scope", return_value=True)
        headers = {}
    conversion.converto.cache_max_size_gb = 1
    mocker.patch.object(conversion_cache, "BYTES_PER_GB", 100)

    response = client.request(
        method,
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers=headers,
        params={"converted": "true"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    assert (cached_copy.stat().st_mtime > time.time() - 60) is (method == "get")
    assert conversion_cache.cleanup_stale_conversions() == (0 if method == "get" else 1)
    assert cached_copy.exists() is (method == "get")
    conversion.convert.assert_not_called()
