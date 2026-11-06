"""Keeps `rom_sibling_groups` in step with `rom_identity_keys`."""

from collections.abc import Collection, Iterable, Iterator
from itertools import batched
from typing import Final

from sqlalchemy import delete, func, insert, select, tuple_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from models.rom import Rom, RomIdentityKey, RomSiblingGroup
from utils.sibling_groups import sibling_groups

IdentityKey = tuple[int, int, str]

# Bound on the parameters one IN list carries.
_CHUNK_SIZE: Final = 500

_KEY_COLUMNS = (
    RomIdentityKey.provider,
    RomIdentityKey.platform_id,
    RomIdentityKey.provider_id,
)


def sibling_group_key() -> ColumnElement[int]:
    """The id a ROM's versions share, needing an outer join to `RomSiblingGroup`."""
    return func.coalesce(RomSiblingGroup.group_id, Rom.id)


def group_keys(session: Session, rom_ids: Collection[int]) -> dict[int, int]:
    """Each ROM's `sibling_group_key`."""
    keys: dict[int, int] = {}
    for chunk in batched(rom_ids, _CHUNK_SIZE, strict=False):
        keys.update(
            (rom_id, group_key)
            for rom_id, group_key in session.execute(
                select(Rom.id, sibling_group_key())
                .outerjoin(RomSiblingGroup, RomSiblingGroup.rom_id == Rom.id)
                .where(Rom.id.in_(chunk))
            ).all()
        )
    return keys


def group_members(session: Session, rom_ids: Collection[int]) -> set[int]:
    """`rom_ids` plus every ROM currently grouped with one of them."""
    members = set(rom_ids)
    for chunk in batched(rom_ids, _CHUNK_SIZE, strict=False):
        group_ids = select(RomSiblingGroup.group_id).where(
            RomSiblingGroup.rom_id.in_(chunk)
        )
        members.update(
            session.scalars(
                select(RomSiblingGroup.rom_id).where(
                    RomSiblingGroup.group_id.in_(group_ids)
                )
            ).all()
        )
    return members


def regroup(session: Session, rom_ids: Collection[int]) -> None:
    """Recompute the groups of `rom_ids` after their identity keys changed.

    Starts from the ROMs' current groups as well, since a ROM that lost a key
    can split the group it leaves behind.
    """
    visited = group_members(session, rom_ids)
    frontier = set(visited)
    seen_keys: set[IdentityKey] = set()
    key_rows: list[tuple[int, IdentityKey]] = []

    while frontier:
        new_keys = {key for _, key in _keys_of_roms(session, frontier)} - seen_keys
        seen_keys |= new_keys
        holders = list(_holders_of_keys(session, new_keys))
        key_rows.extend(holders)
        frontier = {rom_id for rom_id, _ in holders} - visited
        visited |= frontier

    _write(session, sibling_groups(key_rows), scope=visited)


def rebuild(session: Session) -> None:
    """Recompute every group from scratch."""
    rows = session.execute(select(RomIdentityKey.rom_id, *_KEY_COLUMNS)).all()
    groups = sibling_groups(
        (rom_id, (provider, platform_id, provider_id))
        for rom_id, provider, platform_id, provider_id in rows
    )
    _write(session, groups, scope=None)


def _keys_of_roms(
    session: Session, rom_ids: Iterable[int]
) -> Iterator[tuple[int, IdentityKey]]:
    for chunk in batched(rom_ids, _CHUNK_SIZE, strict=False):
        for rom_id, provider, platform_id, provider_id in session.execute(
            select(RomIdentityKey.rom_id, *_KEY_COLUMNS).where(
                RomIdentityKey.rom_id.in_(chunk)
            )
        ).all():
            yield rom_id, (provider, platform_id, provider_id)


def _holders_of_keys(
    session: Session, keys: Iterable[IdentityKey]
) -> Iterator[tuple[int, IdentityKey]]:
    for chunk in batched(keys, _CHUNK_SIZE, strict=False):
        for rom_id, provider, platform_id, provider_id in session.execute(
            select(RomIdentityKey.rom_id, *_KEY_COLUMNS).where(
                tuple_(*_KEY_COLUMNS).in_(chunk)
            )
        ).all():
            yield rom_id, (provider, platform_id, provider_id)


def _write(
    session: Session, groups: dict[int, int], *, scope: Collection[int] | None
) -> None:
    """Store `groups` for the ROMs in `scope` (every ROM when None).

    Only the rows that changed are written, so a rescan that moves nothing
    takes no row locks.
    """
    stored_query = select(RomSiblingGroup.rom_id, RomSiblingGroup.group_id)
    stored: dict[int, int] = {}
    if scope is None:
        stored = {
            rom_id: group_id for rom_id, group_id in session.execute(stored_query).all()
        }
    else:
        for chunk in batched(scope, _CHUNK_SIZE, strict=False):
            stored.update(
                (rom_id, group_id)
                for rom_id, group_id in session.execute(
                    stored_query.where(RomSiblingGroup.rom_id.in_(chunk))
                ).all()
            )

    stale = [
        rom_id for rom_id, group_id in stored.items() if groups.get(rom_id) != group_id
    ]
    fresh = [
        {"rom_id": rom_id, "group_id": group_id}
        for rom_id, group_id in groups.items()
        if stored.get(rom_id) != group_id
    ]

    for chunk in batched(stale, _CHUNK_SIZE, strict=False):
        session.execute(
            delete(RomSiblingGroup).where(RomSiblingGroup.rom_id.in_(chunk))
        )
    for rows in batched(fresh, _CHUNK_SIZE, strict=False):
        session.execute(insert(RomSiblingGroup), list(rows))
