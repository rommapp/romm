import pytest


def _get_fixture(request: pytest.FixtureRequest, *names: str):
    for name in names:
        try:
            return request.getfixturevalue(name)
        except pytest.FixtureLookupError:
            continue
    pytest.fail(f"Missing required fixture. Tried: {', '.join(names)}")


def _request(client, method: str, paths: list[str], **kwargs):
    fn = getattr(client, method)
    last_response = None
    for path in paths:
        response = fn(path, **kwargs)
        last_response = response
        if response.status_code != 404:
            return response, path
    assert last_response is not None
    return last_response, paths[-1]


def _extract_items(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "results", "data", "platforms"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _platform_name(platform: dict) -> str | None:
    for key in ("name", "display_name", "platform_name", "canonical_name"):
        value = platform.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _find_platform(platforms: list[dict], target_name: str) -> dict | None:
    target = target_name.casefold()
    for platform in platforms:
        name = _platform_name(platform)
        if isinstance(name, str) and name.casefold() == target:
            return platform
    return None


def _platform_id(platform: dict):
    for key in ("id", "platform_id"):
        if key in platform:
            return platform[key]
    return None


def _create_platform(client, headers, name: str) -> dict:
    response, _ = _request(
        client,
        "post",
        ["/api/platforms", "/platforms", "/api/v1/platforms"],
        json={"name": name},
        headers=headers,
    )
    assert response.status_code < 400, response.text
    payload = response.json()
    if isinstance(payload, dict):
        if any(key in payload for key in ("id", "platform_id", "name", "display_name")):
            return payload
        for key in ("item", "data", "platform"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested
    pytest.fail(f"Unexpected create platform payload for {name}: {payload}")


def _assign_variant(client, headers, fbneo_id, arcade_id):
    paths = [
        f"/api/platforms/{fbneo_id}",
        f"/platforms/{fbneo_id}",
        f"/api/v1/platforms/{fbneo_id}",
    ]
    payloads = [
        {"parent_platform_id": arcade_id, "is_variant": True},
        {"parent_id": arcade_id, "is_variant": True},
        {"canonical_platform_id": arcade_id},
        {"variant_of": arcade_id},
    ]

    for method in ("patch", "put"):
        for payload in payloads:
            response, _ = _request(client, method, paths, json=payload, headers=headers)
            if response.status_code < 400:
                return
    pytest.fail("Unable to assign FBNeo as a platform variant of Arcade")


def test_arcade_fbneo_variant_assignment_keeps_arcade_canonical_name(request: pytest.FixtureRequest):
    client = _get_fixture(request, "client", "api_client", "test_client")
    headers = None
    try:
        headers = _get_fixture(request, "auth_headers", "admin_headers", "authenticated_headers")
    except Exception:
        headers = None

    arcade = _create_platform(client, headers, "Arcade")
    fbneo = _create_platform(client, headers, "FBNeo")

    arcade_id = _platform_id(arcade)
    fbneo_id = _platform_id(fbneo)

    assert arcade_id is not None, arcade
    assert fbneo_id is not None, fbneo

    _assign_variant(client, headers, fbneo_id, arcade_id)

    response, _ = _request(client, "get", ["/api/platforms", "/platforms", "/api/v1/platforms"], headers=headers)
    assert response.status_code < 400, response.text
    platforms = _extract_items(response.json())

    arcade_after = _find_platform(platforms, "Arcade")
    assert arcade_after is not None, "Arcade should remain present after FBNeo variant assignment"

    canonical_like_fields = ("name", "display_name", "platform_name", "canonical_name")
    observed = {field: arcade_after.get(field) for field in canonical_like_fields if field in arcade_after}
    assert any(value == "Arcade" for value in observed.values()), observed
