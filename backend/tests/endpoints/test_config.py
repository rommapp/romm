from unittest.mock import patch

from fastapi import status

from config.config_manager import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DEFAULT_EXCLUDED_FILES,
)
from config.config_manager import config_manager as cm


def test_config(client):
    response = client.get("/api/config")
    assert response.status_code == status.HTTP_200_OK

    config = response.json()
    assert config.get("EXCLUDED_PLATFORMS") == sorted(DEFAULT_EXCLUDED_DIRS)
    assert config.get("EXCLUDED_SINGLE_EXT") == sorted(
        e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS
    )
    assert config.get("EXCLUDED_SINGLE_FILES") == sorted(DEFAULT_EXCLUDED_FILES)
    assert config.get("EXCLUDED_MULTI_FILES") == sorted(DEFAULT_EXCLUDED_DIRS)
    assert config.get("EXCLUDED_MULTI_PARTS_EXT") == sorted(
        e.lower() for e in DEFAULT_EXCLUDED_EXTENSIONS
    )
    assert config.get("EXCLUDED_MULTI_PARTS_FILES") == sorted(DEFAULT_EXCLUDED_FILES)
    assert config.get("PLATFORMS_BINDING") == {}
    assert not config.get("SKIP_HASH_CALCULATION")
    assert config.get("GAMELIST_MEDIA_THUMBNAIL") == "box2d"
    assert config.get("GAMELIST_MEDIA_IMAGE") == "screenshot"
    assert config.get("GAMELIST_AUTO_EXPORT_ON_SCAN") is False
    assert config.get("PEGASUS_AUTO_EXPORT_ON_SCAN") is False


def test_config_parse_error_gated_by_auth(client, access_token: str):
    # The raw parser error can leak the config file path, so it is only
    # returned to authenticated users.
    cfg = cm.get_config()
    cfg.CONFIG_FILE_PARSE_ERROR = 'in "/data/config.yml", line 2'

    with patch.object(cm, "get_config", return_value=cfg):
        anon = client.get("/api/config")
        assert anon.status_code == status.HTTP_200_OK
        assert anon.json().get("CONFIG_FILE_PARSE_ERROR") is None

        auth = client.get(
            "/api/config",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert auth.status_code == status.HTTP_200_OK
        assert (
            auth.json().get("CONFIG_FILE_PARSE_ERROR")
            == 'in "/data/config.yml", line 2'
        )


def test_add_platform_binding_payload_shape(client, access_token: str):
    with patch.object(cm, "add_platform_binding") as add_platform_binding:
        response = client.post(
            "/api/config/system/platforms",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"fs_slug": "n64", "slug": "nintendo-64"},
        )

    assert response.status_code == status.HTTP_200_OK
    add_platform_binding.assert_called_once_with("n64", "nintendo-64")


def test_add_platform_version_payload_shape(client, access_token: str):
    with patch.object(cm, "add_platform_version") as add_platform_version:
        response = client.post(
            "/api/config/system/versions",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"fs_slug": "n64", "slug": "1.0"},
        )

    assert response.status_code == status.HTTP_200_OK
    add_platform_version.assert_called_once_with("n64", "1.0")


def test_add_exclusion_payload_shape(client, access_token: str):
    with patch.object(cm, "add_exclusion") as add_exclusion:
        response = client.post(
            "/api/config/exclude",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"exclusion_type": "single_files", "exclusion_value": "README.txt"},
        )

    assert response.status_code == status.HTTP_200_OK
    add_exclusion.assert_called_once_with("single_files", "README.txt")


def _scan_payload(**overrides):
    payload = {
        "metadata_priority": ["igdb", "moby"],
        "artwork_priority": ["sgdb", "igdb"],
        "cover_priority": ["igdb", "ss"],
        "screenshot_priority": None,
        "manual_priority": None,
        "region_priority": ["us", "eu"],
        "language_priority": ["en", "fr"],
        "media": ["box2d", "screenshot"],
        "gamelist_export": True,
        "gamelist_thumbnail": "box2d",
        "gamelist_image": "screenshot",
        "pegasus_export": False,
    }
    payload.update(overrides)
    return payload


def test_update_scan_settings_payload_shape(client, access_token: str):
    with patch.object(cm, "update_scan_settings") as update_scan_settings:
        response = client.put(
            "/api/config/scan",
            headers={"Authorization": f"Bearer {access_token}"},
            json=_scan_payload(),
        )

    assert response.status_code == status.HTTP_200_OK
    update_scan_settings.assert_called_once_with(
        metadata_priority=["igdb", "moby"],
        artwork_priority=["sgdb", "igdb"],
        artwork_overrides={
            "cover": ["igdb", "ss"],
            "screenshot": None,
            "manual": None,
        },
        region_priority=["us", "eu"],
        language_priority=["en", "fr"],
        media=["box2d", "screenshot"],
        gamelist_export=True,
        gamelist_thumbnail="box2d",
        gamelist_image="screenshot",
        pegasus_export=False,
    )


def test_update_scan_settings_requires_auth(client):
    response = client.put("/api/config/scan", json=_scan_payload())
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_update_scan_settings_rejects_unknown_source(client, access_token: str):
    with patch.object(cm, "update_scan_settings") as update_scan_settings:
        response = client.put(
            "/api/config/scan",
            headers={"Authorization": f"Bearer {access_token}"},
            json=_scan_payload(metadata_priority=["igdb", "not-a-source"]),
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    update_scan_settings.assert_not_called()


def test_update_scan_settings_rejects_invalid_gamelist_thumbnail(
    client, access_token: str
):
    # `screenshot` is a valid media type but not a valid gamelist thumbnail.
    with patch.object(cm, "update_scan_settings") as update_scan_settings:
        response = client.put(
            "/api/config/scan",
            headers={"Authorization": f"Bearer {access_token}"},
            json=_scan_payload(gamelist_thumbnail="screenshot"),
        )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    update_scan_settings.assert_not_called()


def test_update_scan_settings_normalizes_codes(client, access_token: str):
    with patch.object(cm, "update_scan_settings") as update_scan_settings:
        response = client.put(
            "/api/config/scan",
            headers={"Authorization": f"Bearer {access_token}"},
            json=_scan_payload(
                region_priority=["US", " eu ", "us", ""],
                language_priority=["EN", "en"],
            ),
        )

    assert response.status_code == status.HTTP_200_OK
    _, kwargs = update_scan_settings.call_args
    assert kwargs["region_priority"] == ["us", "eu"]
    assert kwargs["language_priority"] == ["en"]
