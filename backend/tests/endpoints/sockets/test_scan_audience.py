"""Scan events reach only the users who may follow a scan, and of them, a ROM or
platform event only those who can see it."""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import update
from tests.factories import make_esrb_rated_rom, make_rom

from endpoints.responses.rom import SimpleRomSchema
from endpoints.sockets import scan as scan_module
from endpoints.sockets.scan import ScanStats
from handler.auth.permissions import compute_oauth_scopes_by_user
from handler.database import db_permission_handler, db_rom_handler, db_user_handler
from handler.database.base_handler import sync_session
from handler.scan import audience as audience_module
from handler.scan.audience import (
    SCAN_FOLLOWER_SCOPES,
    SCAN_ROOM,
    ScanAudience,
    follows_scans,
    resolve_scan_audience,
)
from handler.scan_handler import emit_scanning_rom
from models.permission import (
    HiddenEntity,
    PermAction,
    PermEntity,
    SystemGroupKey,
    UserPermissionOverride,
)
from models.platform import Platform
from models.rom import Rom, RomVisibility
from models.user import Role, User


def _hide(entity: PermEntity, entity_id: int, user: User) -> None:
    with sync_session.begin() as session:
        session.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user.id))


def _visibility(rom: Rom) -> RomVisibility:
    visibility = db_rom_handler.get_rom_visibility(rom.id)
    assert visibility is not None
    return visibility


def _room(user: User) -> str:
    return f"user:{user.id}"


def test_only_users_who_may_follow_a_scan_are_in_it(
    admin_user: User, editor_user: User, viewer_user: User, platform: Platform
):
    editor_group = db_permission_handler.get_system_group(SystemGroupKey.EDITOR)
    assert editor_group is not None
    db_user_handler.add_user(
        User(
            username="disabled_editor",
            hashed_password="x",
            role=Role.USER,
            enabled=False,
            permission_group_id=editor_group.id,
        )
    )

    rooms = resolve_scan_audience().platform_rooms(platform.id)

    assert sorted(rooms) == sorted([_room(admin_user), _room(editor_user)])


def test_batched_scopes_match_each_users_own(
    admin_user: User, editor_user: User, viewer_user: User
):
    granted = db_user_handler.add_user(
        User(username="granted", hashed_password="x", role=Role.USER)
    )
    with sync_session.begin() as session:
        session.add(
            UserPermissionOverride(
                user_id=granted.id,
                entity=PermEntity.TASKS,
                action=PermAction.WRITE,
                granted=True,
            )
        )
        session.add(
            UserPermissionOverride(
                user_id=editor_user.id,
                entity=PermEntity.PLATFORMS,
                action=PermAction.WRITE,
                granted=False,
            )
        )

    users = db_user_handler.get_users()
    batched = compute_oauth_scopes_by_user(db_user_handler.get_enabled_principals())

    assert {user.id: follows_scans(user) for user in users} == {
        user_id: not SCAN_FOLLOWER_SCOPES.isdisjoint(scopes)
        for user_id, scopes in batched.items()
    }
    assert batched == {user.id: user.oauth_scopes for user in users}


def test_a_rom_event_skips_followers_it_is_hidden_from(
    admin_user: User, editor_user: User, platform: Platform
):
    hidden = make_rom(platform, "hidden")
    shown = make_rom(platform, "shown")
    _hide(PermEntity.ROMS, hidden.id, editor_user)

    audience = resolve_scan_audience()

    assert audience.rom_rooms(_visibility(hidden)) == [_room(admin_user)]
    assert sorted(audience.rom_rooms(_visibility(shown))) == sorted(
        [_room(admin_user), _room(editor_user)]
    )


def test_a_rom_event_follows_the_age_limit(
    admin_user: User, editor_user: User, platform: Platform
):
    mature = make_esrb_rated_rom(platform, "mature", "M")
    with sync_session.begin() as session:
        session.execute(
            update(User).where(User.id == editor_user.id).values(age_limit=12)
        )

    assert resolve_scan_audience().rom_rooms(_visibility(mature)) == [_room(admin_user)]


def test_a_platform_event_skips_followers_it_is_hidden_from(
    admin_user: User,
    editor_user: User,
    platform: Platform,
    other_platform: Platform,
):
    _hide(PermEntity.PLATFORMS, platform.id, editor_user)

    audience = resolve_scan_audience()

    assert audience.platform_rooms(platform.id) == [_room(admin_user)]
    assert len(audience.platform_rooms(other_platform.id)) == 2


class TestEmits:
    @pytest.fixture(autouse=True)
    def payload(self, mocker):
        mocker.patch.object(
            SimpleRomSchema,
            "from_orm_with_factory",
            side_effect=lambda rom, *a, **k: Mock(
                model_dump=Mock(return_value={"id": rom.id})
            ),
        )

    def _audience(self, mocker, rooms: list[str]) -> None:
        audience = Mock(spec=ScanAudience)
        audience.rom_rooms.return_value = rooms
        mocker.patch.object(
            audience_module, "resolve_scan_audience", return_value=audience
        )
        audience_module.begin_scan_audience()

    async def test_a_rom_event_goes_to_its_audience(self, mocker):
        self._audience(mocker, ["user:1", "user:2"])
        socket_manager = AsyncMock()

        await emit_scanning_rom(socket_manager, Rom(id=5, platform_id=1), is_new=True)

        socket_manager.emit.assert_awaited_once_with(
            "scan:scanning_rom", {"id": 5, "is_new": True}, to=["user:1", "user:2"]
        )

    async def test_a_rom_event_nobody_may_see_is_not_broadcast(self, mocker):
        self._audience(mocker, [])
        socket_manager = AsyncMock()

        await emit_scanning_rom(socket_manager, Rom(id=5, platform_id=1), is_new=True)

        socket_manager.emit.assert_not_awaited()

    async def test_progress_goes_to_the_scan_room(self, mocker):
        mocker.patch.object(scan_module, "update_job_meta")
        socket_manager = AsyncMock()

        await ScanStats().update(socket_manager, total_roms=3)

        emitted = socket_manager.emit.await_args
        assert emitted is not None
        assert emitted.args[0] == "scan:update_stats"
        assert emitted.kwargs == {"to": SCAN_ROOM}

    async def test_a_permission_change_refreshes_a_running_scans_audience(self, mocker):
        before, after = Mock(spec=ScanAudience), Mock(spec=ScanAudience)
        resolve = mocker.patch.object(
            audience_module, "resolve_scan_audience", side_effect=[before, after]
        )
        audience_module.begin_scan_audience()
        assert audience_module.current_scan_audience() is before

        audience_module.bump_permissions_generation()

        assert audience_module.current_scan_audience() is after
        assert audience_module.current_scan_audience() is after
        assert resolve.call_count == 2
