from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import ColumnElement, Select, String, cast, delete, func, or_, select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.interfaces import LoaderOption

from decorators.database import begin_session
from models.audit_event import AuditCategory, AuditEvent, actions_in
from models.device import Device
from models.rom import Rom
from models.user import User
from utils.database import LIKE_ESCAPE_CHAR, escape_like

from .base_handler import DBBaseHandler, affected_rows


def _with_actor() -> LoaderOption:
    # Name and avatar only, the rest of a user row is large JSON.
    return joinedload(AuditEvent.actor).load_only(
        User.id, User.username, User.avatar_path, User.updated_at
    )


@dataclass(frozen=True, slots=True)
class AuditEventFilters:
    actor_ids: Collection[int] | None = None
    actions: Collection[str] | None = None
    # Narrows `actions`, or stands for them when none are given.
    categories: Collection[AuditCategory] | None = None
    target_type: str | None = None
    target_id: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    # Pins a paged read to the rows that existed when its first page was fetched.
    max_id: int | None = None
    search: str | None = None
    hidden_rom_ids: Collection[int] = field(default_factory=frozenset)
    hidden_platform_ids: Collection[int] = field(default_factory=frozenset)


def _not_targeting(
    target_type: str, ids: Collection[int] | Select[tuple[str]]
) -> ColumnElement[bool]:
    """Events other than those on the given targets of one type."""
    excluded = ids if isinstance(ids, Select) else [str(i) for i in ids]
    return or_(
        AuditEvent.target_type.is_(None),
        AuditEvent.target_type != target_type,
        AuditEvent.target_id.is_(None),
        AuditEvent.target_id.not_in(excluded),
    )


class DBAuditEventsHandler(DBBaseHandler):
    @begin_session
    def add_events(
        self,
        events: Sequence[AuditEvent],
        session: Session = None,  # type: ignore[assignment]
    ) -> None:
        session.add_all(events)

    @begin_session
    def get_events(
        self,
        filters: AuditEventFilters,
        limit: int,
        offset: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> tuple[list[tuple[AuditEvent, str | None]], int, int | None]:
        """A page of events, newest first, each with its device's name, the total,
        and the highest id among the matches for later pages to be pinned to."""
        clauses: list[ColumnElement[bool]] = []
        if filters.actor_ids is not None:
            clauses.append(AuditEvent.actor_id.in_(filters.actor_ids))
        actions = set(filters.actions) if filters.actions is not None else None
        if filters.categories:
            in_categories: set[str] = {
                a for c in filters.categories for a in actions_in(c)
            }
            actions = in_categories if actions is None else actions & in_categories
        if actions is not None:
            clauses.append(AuditEvent.action.in_(actions))
        if filters.target_type is not None:
            clauses.append(AuditEvent.target_type == filters.target_type)
        if filters.target_id is not None:
            clauses.append(AuditEvent.target_id == filters.target_id)
        if filters.since is not None:
            clauses.append(AuditEvent.occurred_at >= filters.since)
        if filters.until is not None:
            clauses.append(AuditEvent.occurred_at < filters.until)
        if filters.max_id is not None:
            clauses.append(AuditEvent.id <= filters.max_id)
        if filters.search:
            like = f"%{escape_like(filters.search.lower())}%"
            clauses.append(
                or_(
                    *(
                        func.lower(column).like(like, escape=LIKE_ESCAPE_CHAR)
                        for column in (
                            AuditEvent.actor_name,
                            AuditEvent.target_name,
                            AuditEvent.ip_address,
                        )
                    )
                )
            )
        if filters.hidden_rom_ids:
            clauses.append(_not_targeting("rom", filters.hidden_rom_ids))
        if filters.hidden_platform_ids:
            clauses.append(_not_targeting("platform", filters.hidden_platform_ids))
            # A platform's hide covers its roms too.
            clauses.append(
                _not_targeting(
                    "rom",
                    select(cast(Rom.id, String)).where(
                        Rom.platform_id.in_(filters.hidden_platform_ids)
                    ),
                )
            )

        total, highest_id = session.execute(
            select(func.count(), func.max(AuditEvent.id)).where(*clauses)
        ).one()
        rows = session.execute(
            select(AuditEvent, Device.name)
            .options(_with_actor())
            .outerjoin(Device, Device.id == AuditEvent.device_id)
            .where(*clauses)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return (
            [(event, device_name) for event, device_name in rows],
            total or 0,
            highest_id,
        )

    @begin_session
    def delete_batch_before(
        self,
        cutoff: datetime,
        batch_size: int,
        session: Session = None,  # type: ignore[assignment]
    ) -> int:
        """Delete up to `batch_size` of the oldest events from before `cutoff`."""
        # Ids first: MySQL refuses a LIMIT inside an IN subquery.
        ids = session.scalars(
            select(AuditEvent.id)
            .where(AuditEvent.occurred_at < cutoff)
            .order_by(AuditEvent.occurred_at)
            .limit(batch_size)
        ).all()
        if not ids:
            return 0
        result = session.execute(
            delete(AuditEvent)
            .where(AuditEvent.id.in_(ids))
            .execution_options(synchronize_session=False)
        )
        return affected_rows(result)
