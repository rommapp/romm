"""`get_rom_audience` answers what `resolve_permissions` does, user by user."""

from collections.abc import Iterator

import pytest
from tests.factories import make_esrb_rated_rom, make_rom

from handler.auth.permissions import resolve_permissions
from handler.database import db_permission_handler, db_rom_handler, db_user_handler
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity, PermissionGroup
from models.platform import Platform
from models.rom import Rom, RomVisibility
from models.user import Role, User


@pytest.fixture(autouse=True)
def _cleanup_non_system_groups() -> Iterator[None]:
    yield
    with sync_session.begin() as session:
        session.query(PermissionGroup).filter(
            PermissionGroup.system_key.is_(None)
        ).delete(synchronize_session="evaluate")


@pytest.fixture
def default_age_limit() -> Iterator[None]:
    """Give the seeded default group an age limit of 16 for the test."""
    default_id = db_permission_handler.get_default_group_id()
    assert default_id is not None

    def set_limit(age_limit: int | None) -> None:
        with sync_session.begin() as session:
            session.query(PermissionGroup).filter_by(id=default_id).update(
                {"age_limit": age_limit}
            )

    set_limit(16)
    yield
    set_limit(None)


def _group(
    name: str, *, age_limit: int | None = None, hide_unrated: bool = False
) -> int:
    with sync_session.begin() as session:
        group = PermissionGroup(
            name=name, age_limit=age_limit, hide_unrated_roms=hide_unrated
        )
        session.add(group)
        session.flush()
        return group.id


def _user(name: str, **fields: object) -> User:
    return db_user_handler.add_user(
        User(username=name, hashed_password="x", role=Role.USER, **fields)
    )


def _hide(
    entity: PermEntity,
    entity_id: int,
    *,
    user_id: int | None = None,
    group_id: int | None = None,
) -> None:
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=entity, entity_id=entity_id, user_id=user_id, group_id=group_id
            )
        )


def _visibility(rom: Rom) -> RomVisibility:
    visibility = db_rom_handler.get_rom_visibility(rom.id)
    assert visibility is not None
    return visibility


def _resolved(rom: RomVisibility) -> list[int]:
    return sorted(
        user.id
        for user in db_user_handler.get_users()
        if user.enabled and resolve_permissions(user).can_see_rom(rom)
    )


@pytest.fixture
def roms(platform: Platform, other_platform: Platform) -> list[Rom]:
    roms = [
        make_esrb_rated_rom(platform, "rated", "T"),
        make_rom(platform, "unrated"),
        make_esrb_rated_rom(platform, "mature", "M"),
        make_esrb_rated_rom(other_platform, "elsewhere", "E"),
    ]
    # Between the age limits below: 12 hides T, 16 hides M, 18 hides neither.
    assert [_visibility(rom).min_age for rom in roms] == [13, None, 17, 6]
    return roms


def test_matches_the_resolver_for_every_user_and_rom(
    admin_user: User, platform: Platform, roms: list[Rom], default_age_limit: None
):
    rated, unrated, _mature, elsewhere = roms
    hides_rom = _group("No rated")
    teen = _group("Teen", age_limit=12)
    hides_platform = _group("No platform", age_limit=12)
    strict = _group("Strict", hide_unrated=True)
    _hide(PermEntity.ROMS, rated.id, group_id=hides_rom)
    _hide(PermEntity.PLATFORMS, platform.id, group_id=hides_platform)

    _user("defaulted")
    _user("older_than_default", age_limit=18)
    _user("younger_than_default", age_limit=12)
    _user("in_teen", permission_group_id=teen)
    _user("in_hides_rom", permission_group_id=hides_rom)
    _user("in_hides_platform", permission_group_id=hides_platform)
    _user("in_strict", permission_group_id=strict)
    _user("strict_but_not_unrated", permission_group_id=strict, hide_unrated_roms=False)
    _user("unrated_hidden_alone", hide_unrated_roms=True)
    _user("disabled", enabled=False)
    own_hides = _user("own_hides")
    _hide(PermEntity.ROMS, unrated.id, user_id=own_hides.id)
    _hide(PermEntity.PLATFORMS, elsewhere.platform_id, user_id=own_hides.id)
    _hide(PermEntity.ROMS, rated.id, user_id=admin_user.id)

    for rom in roms:
        visibility = _visibility(rom)
        assert db_permission_handler.get_rom_audience(visibility) == _resolved(
            visibility
        ), rom.name


def test_a_group_less_user_follows_an_unrestricted_default(
    admin_user: User, roms: list[Rom]
):
    plain = _user("plain")

    for rom in roms:
        assert db_permission_handler.get_rom_audience(_visibility(rom)) == [
            admin_user.id,
            plain.id,
        ]


def test_the_query_count_does_not_grow_with_the_users(
    admin_user: User, roms: list[Rom], executed_statements: list[str]
):
    visibility = _visibility(roms[0])
    _user("first")
    executed_statements.clear()
    db_permission_handler.get_rom_audience(visibility)
    with_two = len(executed_statements)

    for n in range(8):
        _user(f"more_{n}")
    executed_statements.clear()
    db_permission_handler.get_rom_audience(visibility)

    assert len(executed_statements) == with_two
