"""Sweeps over every registered route, so a new route can't skip auth or visibility."""

import re
from collections.abc import Iterable, Iterator

from fastapi import status
from fastapi.routing import APIRoute
from main import app
from starlette.routing import BaseRoute
from tests.endpoints.test_permissions_visibility import _auth, _hide

from decorators.auth import oauth2_password_bearer
from models.permission import PermEntity

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
            yield from _walk(route.original_router.routes, prefix + context.prefix)


def _api_routes() -> list[tuple[str, APIRoute]]:
    routes = [(path, r) for path, r in _walk(app.routes, "") if path.startswith("/api")]
    assert routes, "route discovery found nothing; the sweep would pass vacuously"
    return routes


def _is_protected(route: APIRoute) -> bool:
    return any(dep.dependency is oauth2_password_bearer for dep in route.dependencies)


def test_every_api_route_requires_auth_or_is_listed_public():
    unguarded = sorted(
        f"{','.join(sorted(route.methods))} {path} -> {_handler_name(route)}"
        for path, route in _api_routes()
        if not _is_protected(route) and _handler_name(route) not in PUBLIC_API_HANDLERS
    )
    assert unguarded == []


MISSING_ID = 987654321
_ENTITY_PATH = re.compile(
    r"^/api/(roms|platforms|firmware|activity/rom)/\{(id|rom_id)\}"
)
# Values for the path parameters a route takes beside the entity id.
_OTHER_PARAMS = {"file_id": "1", "note_id": "1", "file_name": "x", "path": "x"}
_ROM_SEGMENTS = ("roms", "activity/rom")


def _entity_routes(segments: tuple[str, ...]) -> list[tuple[str, str, str]]:
    found = set()
    for path, route in _api_routes():
        match = _ENTITY_PATH.match(path)
        if path.endswith("/") or not match or match.group(1) not in segments:
            continue
        for method in route.methods:
            found.add((match.group(1), method, path))
    assert found, f"no route keyed on {segments}; the sweep would pass vacuously"
    return sorted(found)


def _fill(path: str, entity_id: int) -> str:
    path = re.sub(r"\{(id|rom_id)\}", str(entity_id), path, count=1)
    return re.sub(r"\{(\w+)(:path)?\}", lambda m: _OTHER_PARAMS[m.group(1)], path)


def _leaks(client, headers, routes, ids: dict[str, int]) -> list[str]:
    leaks = []
    for segment, method, path in routes:
        hidden = client.request(method, _fill(path, ids[segment]), headers=headers)
        missing = client.request(method, _fill(path, MISSING_ID), headers=headers)
        same = hidden.status_code == missing.status_code and (
            hidden.status_code >= status.HTTP_400_BAD_REQUEST
            or hidden.content == missing.content
        )
        if not same:
            leaks.append(
                f"{method} {path}: {hidden.status_code} vs {missing.status_code}"
            )
    return leaks


def test_every_entity_route_answers_a_hidden_id_like_a_missing_one(
    client, editor_user, rom, firmware
):
    """A hidden rom, platform or firmware is indistinguishable from one that doesn't exist."""
    headers = _auth(editor_user)

    _hide(PermEntity.ROMS, rom.id, editor_user.id)
    rom_ids = dict.fromkeys(_ROM_SEGMENTS, rom.id)
    leaks = _leaks(client, headers, _entity_routes(_ROM_SEGMENTS), rom_ids)

    _hide(PermEntity.PLATFORMS, rom.platform_id, editor_user.id)
    platform_ids = {"platforms": rom.platform_id, "firmware": firmware.id}
    leaks += _leaks(
        client, headers, _entity_routes(("platforms", "firmware")), platform_ids
    )

    assert leaks == []
