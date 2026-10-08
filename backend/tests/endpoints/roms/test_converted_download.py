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
from config.config_manager import ConvertoConfig
from models.rom import Rom
from utils import conversion_cache
from utils.conversion_cache import FAILED_FILE, RETRY_AFTER_SECONDS


@pytest.fixture
def conversion(tmp_path: Path, mocker):
    """Enable download conversion with every rom-converto step mocked.

    Any listed target resolves to a CHD under a temporary cache, and a
    conversion writes it there.
    """
    converto = ConvertoConfig(download_conversion_enabled=True)
    mocker.patch(
        "utils.conversion_cache.cm.get_config",
        return_value=SimpleNamespace(CONVERTO=converto),
    )
    mocker.patch(
        "utils.conversion_cache.rom_converto_service.is_enabled",
        AsyncMock(return_value=True),
    )
    final = tmp_path / "converts/1-abc/test_rom.chd"
    final.parent.mkdir(parents=True)
    resolved = resolve_operation("psp", "chd", "test_rom.iso")
    assert resolved is not None
    lookup = mocker.patch.object(
        conversion_cache, "_lookup", return_value=(resolved[0], final)
    )
    mocker.patch.object(conversion_cache, "CACHE_BASE_PATH", str(tmp_path))
    mocker.patch.object(
        conversion_cache, "ROM_CONVERTO_CACHE_PATH", str(final.parent.parent)
    )

    async def convert(*args, **kwargs) -> Path:
        final.write_bytes(b"x" * 120)
        return final

    return SimpleNamespace(
        converto=converto,
        final=final,
        lookup=lookup,
        convert=mocker.patch.object(
            conversion_cache, "get_or_convert", AsyncMock(side_effect=convert)
        ),
    )


@pytest.fixture
def cached_copy(conversion) -> Path:
    final: Path = conversion.final
    final.write_bytes(b"x" * 120)
    served = time.time() - 3600
    os.utime(final, (served, served))
    return final


def _redirect(response) -> str:
    return unquote(response.headers["X-Accel-Redirect"])


def _download(client: TestClient, rom: Rom, *, token: str | None, **params):
    return client.get(
        f"/api/roms/{rom.id}/content/test_rom.zip",
        headers={"Authorization": f"Bearer {token}"} if token else {},
        params=params,
        follow_redirects=False,
    )


def _as_kiosk(mocker) -> None:
    mocker.patch("handler.auth.hybrid_auth.KIOSK_MODE", True)
    mocker.patch("handler.auth.permissions.KIOSK_MODE", True)


def test_download_is_untouched_without_a_format(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    response = _download(client, rom, token=access_token)

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.lookup.assert_not_called()
    conversion.convert.assert_not_called()


@pytest.mark.parametrize("formats", ["zip", "chd,zip", " ZIP "])
def test_a_listed_stored_format_serves_the_stored_file(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, formats
):
    response = _download(client, rom, token=access_token, format=formats)

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == f"/library/{rom_file.full_path}"
    conversion.convert.assert_not_called()


def test_a_listed_stored_format_is_served_with_conversion_disabled(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    conversion.converto.download_conversion_enabled = False

    response = _download(client, rom, token=access_token, format="zip")

    assert _redirect(response) == f"/library/{rom_file.full_path}"


def test_a_cached_copy_is_served_without_converting(
    client: TestClient, access_token: str, rom: Rom, rom_file, cached_copy, conversion
):
    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    assert "test_rom.chd" in response.headers["Content-Disposition"]
    conversion.convert.assert_not_called()


def test_a_quick_conversion_is_served_by_the_same_request(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    conversion.convert.assert_awaited_once()


def test_a_slow_conversion_answers_202_and_keeps_running(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch.object(conversion_cache, "CONVERSION_WAIT_SECONDS", 0.01)

    final: Path = conversion.final

    async def slow_convert(*args, **kwargs) -> Path:
        await asyncio.sleep(0.2)
        return final

    conversion.convert.side_effect = slow_convert

    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.headers["Retry-After"] == str(RETRY_AFTER_SECONDS)
    assert "X-Accel-Redirect" not in response.headers
    conversion.convert.assert_called_once()


def test_a_running_conversion_answers_202_without_starting_another(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion, mocker
):
    mocker.patch.object(conversion_cache, "_is_converting", return_value=True)

    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_202_ACCEPTED
    conversion.convert.assert_not_called()


def test_head_reports_202_or_the_cached_copy_but_never_converts(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"/api/roms/{rom.id}/content/test_rom.zip"

    uncached = client.head(url, headers=headers, params={"format": "chd"})
    conversion.final.write_bytes(b"x")
    cached = client.head(url, headers=headers, params={"format": "chd"})

    assert uncached.status_code == status.HTTP_202_ACCEPTED
    assert _redirect(cached) == "/cache/converts/1-abc/test_rom.chd"
    conversion.convert.assert_not_called()


def test_a_kiosk_visitor_never_starts_a_conversion(
    client: TestClient, rom: Rom, rom_file, conversion, mocker
):
    _as_kiosk(mocker)

    response = _download(client, rom, token=None, format="chd")

    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    conversion.convert.assert_not_called()


def test_a_kiosk_visitor_still_gets_a_cached_copy(
    client: TestClient, rom: Rom, rom_file, cached_copy, conversion, mocker
):
    _as_kiosk(mocker)

    response = _download(client, rom, token=None, format="chd")

    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"


def test_no_producible_format_answers_406(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    conversion.lookup.return_value = None

    response = _download(client, rom, token=access_token, format="rvz,wbfs")

    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    assert "rvz, wbfs" in response.json()["detail"]
    conversion.convert.assert_not_called()


def test_disabled_conversion_answers_406_for_another_format(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    conversion.converto.download_conversion_enabled = False

    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    conversion.lookup.assert_not_called()


def test_a_failed_conversion_is_not_retried(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    (conversion.final.parent / FAILED_FILE).touch()

    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE
    conversion.convert.assert_not_called()


def test_a_conversion_that_fails_answers_406(
    client: TestClient, access_token: str, rom: Rom, rom_file, conversion
):
    conversion.convert.side_effect = None
    conversion.convert.return_value = None

    response = _download(client, rom, token=access_token, format="chd")

    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE


def test_a_format_needs_a_single_file(
    client: TestClient, access_token: str, multi_file_rom: Rom, conversion
):
    response = client.head(
        f"/api/roms/{multi_file_rom.id}/content/test_multi_file_rom.zip",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"format": "chd"},
    )

    assert response.status_code == status.HTTP_406_NOT_ACCEPTABLE


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
        _as_kiosk(mocker)
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
        params={"format": "chd"},
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_200_OK
    assert _redirect(response) == "/cache/converts/1-abc/test_rom.chd"
    assert (cached_copy.stat().st_mtime > time.time() - 60) is (method == "get")
    assert conversion_cache.cleanup_stale_conversions() == (0 if method == "get" else 1)
    assert cached_copy.exists() is (method == "get")
    conversion.convert.assert_not_called()
