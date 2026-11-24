"""Keeps `rom_sibling_groups` in step with `rom_identity_keys`."""

from collections.abc import Callable, Collection, Iterable, Iterator
from itertools import batched
from typing import Any, Final

from sqlalchemy import Insert, Row, delete, func, select, tuple_
from sqlalchemy.dialects import mysql as sa_mysql
from sqlalchemy.dialects import postgresql as sa_pg
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from models.rom import Rom, RomIdentityKey, RomSiblingGroup
from utils.database import is_postgresql
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


def group_keys(
    session: Session, rom_ids: Collection[int], *, present_only: bool = False
) -> dict[int, int]:
    """Each ROM's `sibling_group_key`, skipping ROMs off disk when `present_only`."""
    query = select(Rom.id, sibling_group_key()).outerjoin(
        RomSiblingGroup, RomSiblingGroup.rom_id == Rom.id
    )
    if present_only:
        query = query.where(Rom.missing_from_fs.is_(False))
    keys: dict[int, int] = {}
    for chunk in batched(rom_ids, _CHUNK_SIZE, strict=False):
        keys.update(
            (rom_id, group_key)
            for rom_id, group_key in session.execute(
                query.where(Rom.id.in_(chunk))
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
    """Recompute the groups of `rom_ids` after their identity keys changed."""
    # Their current groups too, since a ROM that lost a key can split the one it left.
    visited = group_members(session, rom_ids)
    frontier = set(visited)
    seen_keys: set[IdentityKey] = set()
    key_rows: list[tuple[int, IdentityKey]] = []

    while frontier:
        new_keys = {
            key for _, key in _key_rows(session, frontier, RomIdentityKey.rom_id.in_)
        } - seen_keys
        seen_keys |= new_keys
        holders = list(_key_rows(session, new_keys, tuple_(*_KEY_COLUMNS).in_))
        key_rows.extend(holders)
        frontier = {rom_id for rom_id, _ in holders} - visited
        visited |= frontier

    _write(session, sibling_groups(key_rows), scope=visited)


def rebuild(session: Session) -> None:
    """Recompute every group from scratch."""
    rows = session.execute(select(RomIdentityKey.rom_id, *_KEY_COLUMNS)).all()
    _write(session, sibling_groups(_as_key_rows(rows)), scope=None)


def _key_rows(
    session: Session,
    values: Iterable[Any],
    matches: Callable[[tuple[Any, ...]], ColumnElement[bool]],
) -> Iterator[tuple[int, IdentityKey]]:
    """The key rows `matches` selects, querying `values` a chunk at a time."""
    for chunk in batched(values, _CHUNK_SIZE, strict=False):
        yield from _as_key_rows(
            session.execute(
                select(RomIdentityKey.rom_id, *_KEY_COLUMNS).where(matches(chunk))
            ).all()
        )


def _as_key_rows(
    rows: Iterable[Row[int, int, int, str]],
) -> Iterator[tuple[int, IdentityKey]]:
    for rom_id, provider, platform_id, provider_id in rows:
        yield rom_id, (provider, platform_id, provider_id)


def _write(
    session: Session, groups: dict[int, int], *, scope: Collection[int] | None
) -> None:
    """Store `groups` for the ROMs in `scope` (every ROM when None)."""
    # Only the rows that changed are written, so a rescan that moves nothing
    # takes no row locks.
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

    # Sorted, so two writers lock shared rows in the same order.
    stale = sorted(rom_id for rom_id in stored if rom_id not in groups)
    fresh = [
        {"rom_id": rom_id, "group_id": group_id}
        for rom_id, group_id in sorted(groups.items())
        if stored.get(rom_id) != group_id
    ]

    for chunk in batched(stale, _CHUNK_SIZE, strict=False):
        session.execute(
            delete(RomSiblingGroup).where(RomSiblingGroup.rom_id.in_(chunk))
        )
    for rows in batched(fresh, _CHUNK_SIZE, strict=False):
        session.execute(_upsert(session, list(rows)))


def _upsert(session: Session, rows: list[dict[str, int]]) -> Insert:
    """Insert `rows`, moving a row another writer committed since this one read it."""
    if is_postgresql(session.get_bind()):
        pg_insert = sa_pg.insert(RomSiblingGroup).values(rows)
        return pg_insert.on_conflict_do_update(
            index_elements=["rom_id"],
            set_={"group_id": pg_insert.excluded.group_id},
        )
    mysql_insert = sa_mysql.insert(RomSiblingGroup).values(rows)
    return mysql_insert.on_duplicate_key_update(group_id=mysql_insert.inserted.group_id)
