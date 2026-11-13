"""Sweeps over every registered route, so a new route can't skip auth or visibility."""

import inspect
import re
from collections.abc import Iterable, Iterator
from types import FunctionType
from typing import Any, cast

from fastapi import status
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from httpx2 import Response
from main import app
from sqlalchemy import delete
from starlette.routing import BaseRoute
from tests.endpoints.test_permissions_visibility import _auth, _hide

from decorators.auth import _requires_scopes, oauth2_password_bearer
from handler.database import db_user_handler
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity

# Handlers that answer callers without protected_route; each checks the caller itself.
PUBLIC_API_HANDLERS: frozenset[str] = frozenset(
    {
        "endpoints.auth.auth_openid",
        "endpoints.auth.login",
        "endpoints.auth.login_via_openid",
        "endpoints.auth.logout",
        "endpoints.auth.request_password_reset",
        "endpoints.auth.reset_password",
        "endpoints.auth.token",
        "endpoints.client_tokens.exchange_pair_code",
        "endpoints.client_tokens.pair_status",
        "endpoints.configs.get_config",
        "endpoints.device.auth.device_auth_init",
        "endpoints.device.auth.token",
        "endpoints.heartbeat.heartbeat",
        "endpoints.heartbeat.metadata_heartbeat",
        "endpoints.user.create_user_from_invite",
        # RetroArch's WebDAV verbs authenticate through _authorize in their module.
        "endpoints.sync.retroarch.retroarch_sync_delete",
        "endpoints.sync.retroarch.retroarch_sync_get",
        "endpoints.sync.retroarch.retroarch_sync_lock",
        "endpoints.sync.retroarch.retroarch_sync_mkcol",
        "endpoints.sync.retroarch.retroarch_sync_options",
        "endpoints.sync.retroarch.retroarch_sync_propfind",
        "endpoints.sync.retroarch.retroarch_sync_put",
        "endpoints.sync.retroarch.retroarch_sync_unlock",
        # protected_route with no scopes; each checks scopes in its body.
        "endpoints.client_tokens.delete_token",
        "endpoints.heartbeat.create_setup_platforms",
        "endpoints.heartbeat.get_setup_library_info",
        "endpoints.user.add_user",
        "endpoints.user.create_invite_link",
    }
)


def _handler_name(route: APIRoute) -> str:
    return f"{route.endpoint.__module__}.{route.endpoint.__name__}"


def _walk(routes: Iterable[BaseRoute], prefix: str) -> Iterator[tuple[str, APIRoute]]:
    # Included routers stay lazy (`_IncludedRouter`), so descend into each by hand.
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
        elif (context := getattr(route, "include_context", None)) is not None:
            router = cast(Any, route).original_router
            yield from _walk(router.routes, prefix + context.prefix)


def _api_routes() -> list[tuple[str, APIRoute]]:
    routes = [(path, r) for path, r in _walk(app.routes, "") if path.startswith("/api")]
    assert routes, "route discovery found nothing; the sweep would pass vacuously"
    return routes


def _is_protected(route: APIRoute) -> bool:
    # The bearer dependency only documents the scopes; the endpoint's
    # _requires_scopes wrapper is what rejects, so both must be present.
    declared = any(
        dep.dependency is oauth2_password_bearer and getattr(dep, "scopes", None)
        for dep in route.dependencies
    )
    endpoint = cast(FunctionType, route.endpoint)
    if not endpoint.__code__.co_qualname.startswith(f"{_requires_scopes.__name__}."):
        return False
    return declared and bool(inspect.getclosurevars(endpoint).nonlocals.get("scopes"))


def test_every_api_route_requires_auth_or_is_listed_public():
    unguarded = sorted(
        f"{','.join(sorted(route.methods or ()))} {path} -> {_handler_name(route)}"
        for path, route in _api_routes()
        if not _is_protected(route) and _handler_name(route) not in PUBLIC_API_HANDLERS
    )
    assert unguarded == []


MISSING_ID = 987654321
_ENTITY_PATH = re.compile(
    r"^/api/(roms|platforms|firmware|activity/rom|streaming/states)/\{(id|rom_id)\}"
)
# Routes whose `{id}` is a RomFile id rather than a Rom id.
_ROM_FILE_PATHS = frozenset(
    {
        "/api/roms/{id}/files",
        "/api/roms/{id}/files/content/{file_name}",
        "/api/roms/{id}/patch",
    }
)
_OTHER_PARAMS = {"note_id": "1", "file_name": "x", "path": "x"}
_ROM_SEGMENTS = ("roms", "activity/rom", "streaming/states")
# Answers that come before the entity lookup, so hidden and missing match vacuously.
_NOT_REACHED = frozenset(
    {
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
)


def _entity_routes(segments: tuple[str, ...]) -> list[tuple[str, str, str]]:
    found = set()
    for path, route in _api_routes():
        match = _ENTITY_PATH.match(path)
        if path.endswith("/") or not match or match.group(1) not in segments:
            continue
        for method in route.methods or ():
            found.add((match.group(1), method, path))
    assert found, f"no route keyed on {segments}; the sweep would pass vacuously"
    return sorted(found)


def _fill(path: str, entity_id: int, file_id: int) -> str:
    path = re.sub(r"\{(id|rom_id)\}", str(entity_id), path, count=1)
    params = {**_OTHER_PARAMS, "file_id": str(file_id)}
    return re.sub(r"\{(\w+)(:path)?\}", lambda m: params[m.group(1)], path)


def _request(
    client: TestClient, headers: dict[str, str], method: str, url: str, file_id: int
) -> Response:
    # Valid enough to pass request validation, so the handler's lookup answers.
    if url.endswith("/patch"):
        return client.request(
            method, url, headers=headers, data={"patch_file_id": str(file_id)}
        )
    return client.request(
        method,
        url,
        headers={**headers, "x-upload-filename": "x.bin"},
        json={} if method in {"POST", "PUT"} else None,
    )


def _normalized(response: Response, entity_id: int) -> str:
    return re.sub(rf"\b{entity_id}\b", "<id>", response.text)


def _leaks(client, headers, routes, ids: dict[str, int], file_id: int) -> list[str]:
    leaks = []
    for segment, method, path in routes:
        hidden_id = file_id if path in _ROM_FILE_PATHS else ids[segment]
        hidden_url = _fill(path, hidden_id, file_id)
        hidden = _request(client, headers, method, hidden_url, file_id)
        missing_url = _fill(path, MISSING_ID, file_id)
        missing = _request(client, headers, method, missing_url, file_id)
        if hidden.status_code in _NOT_REACHED:
            leaks.append(
                f"{method} {path}: {hidden.status_code}, never reached the visibility check"
            )
        elif hidden.status_code != missing.status_code or _normalized(
            hidden, hidden_id
        ) != _normalized(missing, MISSING_ID):
            leaks.append(
                f"{method} {path}: {hidden.status_code} {hidden.text[:80]!r}"
                f" vs {missing.status_code} {missing.text[:80]!r}"
            )
    return leaks


def _unhide_all(user_id: int) -> None:
    with sync_session.begin() as s:
        s.execute(delete(HiddenEntity).where(HiddenEntity.user_id == user_id))


def test_every_entity_route_answers_a_hidden_id_like_a_missing_one(
    client, editor_user, rom, rom_file, firmware
):
    """A hidden rom, platform or firmware is indistinguishable from one that doesn't exist."""
    headers = _auth(editor_user)
    rom_routes = _entity_routes(_ROM_SEGMENTS)
    rom_ids = dict.fromkeys(_ROM_SEGMENTS, rom.id)

    _hide(PermEntity.ROMS, rom.id, editor_user.id)
    leaks = [
        f"rom hidden: {leak}"
        for leak in _leaks(client, headers, rom_routes, rom_ids, rom_file.id)
    ]
    _unhide_all(editor_user.id)

    _hide(PermEntity.PLATFORMS, rom.platform_id, editor_user.id)
    leaks += [
        f"platform hidden: {leak}"
        for leak in _leaks(client, headers, rom_routes, rom_ids, rom_file.id)
    ]
    platform_ids = {"platforms": rom.platform_id, "firmware": firmware.id}
    platform_routes = _entity_routes(("platforms", "firmware"))
    leaks += [
        f"platform hidden: {leak}"
        for leak in _leaks(client, headers, platform_routes, platform_ids, rom_file.id)
    ]
    _unhide_all(editor_user.id)

    db_user_handler.update_user(editor_user.id, {"hide_unrated_roms": True})
    leaks += [
        f"unrated hidden: {leak}"
        for leak in _leaks(client, headers, rom_routes, rom_ids, rom_file.id)
    ]

    assert leaks == []
