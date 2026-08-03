from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, cast, delete, distinct, func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from decorators.database import begin_session
from endpoints.responses.downloads import (
    DownloadLogEntry,
    DownloadLogPage,
    DownloadSourceStat,
    DownloadStatsSummary,
    DownloadTimelinePoint,
    PlatformDownloadStat,
    TopDownloadedRom,
)
from models.download_event import DownloadEvent, DownloadKind, DownloadSource
from models.platform import Platform
from models.rom import Rom, RomFile

from .base_handler import DBBaseHandler

MAX_LOG_PAGE_SIZE = 200
MAX_TOP_ROMS = 100


def _rom_size_subquery():
    """Per-rom byte total, matching how the server-wide filesize stat is computed."""
    return (
        select(
            RomFile.rom_id.label("rom_id"),
            func.coalesce(func.sum(RomFile.file_size_bytes), 0).label("size_bytes"),
        )
        .group_by(RomFile.rom_id)
        .subquery()
    )


def _serialize_event(event: DownloadEvent) -> DownloadLogEntry:
    return DownloadLogEntry(
        id=event.id,
        user_id=event.user_id,
        username=event.username,
        rom_id=event.rom_id,
        rom_name=event.rom_name,
        platform_id=event.platform_id,
        platform_name=event.platform_name,
        source=str(event.source),
        kind=str(event.kind),
        file_count=event.file_count,
        size_bytes=event.size_bytes,
        client_ip=event.client_ip,
        user_agent=event.user_agent,
        downloaded_at=event.downloaded_at,
    )


class DBDownloadsHandler(DBBaseHandler):
    @begin_session
    def record_download(
        self,
        rom: Rom,
        username: str,
        source: DownloadSource,
        kind: DownloadKind,
        file_count: int,
        size_bytes: int,
        user_id: int | None = None,
        client_ip: str | None = None,
        user_agent: str | None = None,
        session: Session = None,  # type: ignore
    ) -> DownloadEvent:
        """Log a download and bump the rom's denormalized counters."""
        now = datetime.now(timezone.utc)

        event = DownloadEvent(
            user_id=user_id,
            rom_id=rom.id,
            platform_id=rom.platform_id,
            username=username,
            rom_name=rom.name or rom.fs_name,
            platform_name=rom.platform_display_name,
            source=source,
            kind=kind,
            file_count=file_count,
            size_bytes=size_bytes,
            client_ip=client_ip,
            user_agent=user_agent,
            downloaded_at=now,
        )
        session.add(event)

        # Bump in SQL rather than read-modify-write so concurrent downloads of
        # the same rom can't lose an increment.
        session.execute(
            update(Rom)
            .where(Rom.id == rom.id)
            .values(
                download_count=Rom.download_count + 1,
                last_downloaded_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        session.flush()
        return event

    @begin_session
    def get_download_log(
        self,
        limit: int = 50,
        offset: int = 0,
        rom_id: int | None = None,
        user_id: int | None = None,
        platform_id: int | None = None,
        source: DownloadSource | None = None,
        since: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> DownloadLogPage:
        """Paginated per-download log, newest first."""
        limit = max(1, min(limit, MAX_LOG_PAGE_SIZE))
        offset = max(0, offset)

        filters = []
        if rom_id is not None:
            filters.append(DownloadEvent.rom_id == rom_id)
        if user_id is not None:
            filters.append(DownloadEvent.user_id == user_id)
        if platform_id is not None:
            filters.append(DownloadEvent.platform_id == platform_id)
        if source is not None:
            filters.append(DownloadEvent.source == source)
        if since is not None:
            filters.append(DownloadEvent.downloaded_at >= since)

        total = (
            session.scalar(
                select(func.count()).select_from(DownloadEvent).where(*filters)
            )
            or 0
        )

        events = (
            session.scalars(
                select(DownloadEvent)
                .where(*filters)
                .order_by(DownloadEvent.downloaded_at.desc(), DownloadEvent.id.desc())
                .limit(limit)
                .offset(offset)
            )
            .unique()
            .all()
        )

        return DownloadLogPage(
            items=[_serialize_event(e) for e in events],
            total=total,
            limit=limit,
            offset=offset,
        )

    @begin_session
    def get_summary(
        self,
        since: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> DownloadStatsSummary:
        """Headline counters for the admin overview."""
        totals = session.execute(
            select(
                func.count(DownloadEvent.id),
                func.coalesce(func.sum(DownloadEvent.size_bytes), 0),
                func.count(distinct(DownloadEvent.rom_id)),
                func.count(distinct(DownloadEvent.user_id)),
            )
        ).one()

        if since is not None:
            windowed_row = session.execute(
                select(
                    func.count(DownloadEvent.id),
                    func.coalesce(func.sum(DownloadEvent.size_bytes), 0),
                ).where(DownloadEvent.downloaded_at >= since)
            ).one()
            windowed_count, windowed_bytes = windowed_row[0], windowed_row[1]
        else:
            windowed_count, windowed_bytes = totals[0], totals[1]

        roms_total = session.scalar(select(func.count()).select_from(Rom)) or 0

        size_sq = _rom_size_subquery()
        never = session.execute(
            select(
                func.count(Rom.id),
                func.coalesce(func.sum(size_sq.c.size_bytes), 0),
            )
            .select_from(Rom)
            .outerjoin(size_sq, size_sq.c.rom_id == Rom.id)
            .where(Rom.download_count == 0)
        ).one()

        return DownloadStatsSummary(
            total_downloads=int(totals[0] or 0),
            total_bytes=int(totals[1] or 0),
            downloads_in_window=int(windowed_count or 0),
            bytes_in_window=int(windowed_bytes or 0),
            unique_roms_downloaded=int(totals[2] or 0),
            unique_users=int(totals[3] or 0),
            roms_total=roms_total,
            never_downloaded_count=int(never[0] or 0),
            never_downloaded_bytes=int(never[1] or 0),
        )

    @begin_session
    def get_top_roms(
        self,
        limit: int = 10,
        since: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> list[TopDownloadedRom]:
        """Most-downloaded roms. Without `since` this reads the denormalized
        counter; with one it counts events inside the window."""
        limit = max(1, min(limit, MAX_TOP_ROMS))
        size_sq = _rom_size_subquery()

        if since is None:
            rows = session.execute(
                select(
                    Rom.id,
                    Rom.name,
                    Rom.fs_name,
                    Rom.platform_id,
                    Platform.name,
                    Platform.custom_name,
                    Platform.slug,
                    Rom.path_cover_s,
                    Rom.download_count,
                    Rom.last_downloaded_at,
                    func.coalesce(size_sq.c.size_bytes, 0),
                )
                .join(Platform, Platform.id == Rom.platform_id)
                .outerjoin(size_sq, size_sq.c.rom_id == Rom.id)
                .where(Rom.download_count > 0)
                .order_by(Rom.download_count.desc(), Rom.id.asc())
                .limit(limit)
            ).all()
        else:
            counts_sq = (
                select(
                    DownloadEvent.rom_id.label("rom_id"),
                    func.count(DownloadEvent.id).label("download_count"),
                    func.max(DownloadEvent.downloaded_at).label("last_downloaded_at"),
                )
                .where(
                    DownloadEvent.downloaded_at >= since,
                    DownloadEvent.rom_id.is_not(None),
                )
                .group_by(DownloadEvent.rom_id)
                .subquery()
            )
            rows = session.execute(
                select(
                    Rom.id,
                    Rom.name,
                    Rom.fs_name,
                    Rom.platform_id,
                    Platform.name,
                    Platform.custom_name,
                    Platform.slug,
                    Rom.path_cover_s,
                    counts_sq.c.download_count,
                    counts_sq.c.last_downloaded_at,
                    func.coalesce(size_sq.c.size_bytes, 0),
                )
                .join(counts_sq, counts_sq.c.rom_id == Rom.id)
                .join(Platform, Platform.id == Rom.platform_id)
                .outerjoin(size_sq, size_sq.c.rom_id == Rom.id)
                .order_by(counts_sq.c.download_count.desc(), Rom.id.asc())
                .limit(limit)
            ).all()

        return [
            TopDownloadedRom(
                rom_id=row[0],
                rom_name=row[1] or row[2],
                platform_id=row[3],
                platform_name=row[5] or row[4],
                platform_slug=row[6],
                path_cover_small=row[7] or None,
                download_count=int(row[8] or 0),
                last_downloaded_at=row[9],
                file_size_bytes=int(row[10] or 0),
            )
            for row in rows
        ]

    @begin_session
    def get_downloads_by_platform(
        self,
        since: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> list[PlatformDownloadStat]:
        filters: list[ColumnElement[bool]] = [DownloadEvent.platform_id.is_not(None)]
        if since is not None:
            filters.append(DownloadEvent.downloaded_at >= since)

        rows = session.execute(
            select(
                Platform.id,
                Platform.name,
                Platform.custom_name,
                Platform.slug,
                func.count(DownloadEvent.id),
                func.coalesce(func.sum(DownloadEvent.size_bytes), 0),
            )
            .join(Platform, Platform.id == DownloadEvent.platform_id)
            .where(*filters)
            .group_by(Platform.id, Platform.name, Platform.custom_name, Platform.slug)
            .order_by(func.count(DownloadEvent.id).desc())
        ).all()

        return [
            PlatformDownloadStat(
                platform_id=row[0],
                platform_name=row[2] or row[1],
                platform_slug=row[3],
                download_count=int(row[4] or 0),
                size_bytes=int(row[5] or 0),
            )
            for row in rows
        ]

    @begin_session
    def get_downloads_by_source(
        self,
        since: datetime | None = None,
        session: Session = None,  # type: ignore
    ) -> list[DownloadSourceStat]:
        filters = []
        if since is not None:
            filters.append(DownloadEvent.downloaded_at >= since)

        rows = session.execute(
            select(DownloadEvent.source, func.count(DownloadEvent.id))
            .where(*filters)
            .group_by(DownloadEvent.source)
            .order_by(func.count(DownloadEvent.id).desc())
        ).all()

        return [
            DownloadSourceStat(source=str(row[0]), count=int(row[1] or 0))
            for row in rows
        ]

    @begin_session
    def get_timeline(
        self,
        days: int = 30,
        session: Session = None,  # type: ignore
    ) -> list[DownloadTimelinePoint]:
        """Daily download counts for the last `days` days, gap-filled with zeros."""
        days = max(1, min(days, 365))
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days - 1)

        # CAST to DATE rather than a dialect-specific date function, so the
        # grouping works the same on MariaDB, MySQL and Postgres.
        day_col = cast(DownloadEvent.downloaded_at, Date).label("day")
        rows = session.execute(
            select(
                day_col,
                func.count(DownloadEvent.id),
                func.coalesce(func.sum(DownloadEvent.size_bytes), 0),
            )
            .where(
                DownloadEvent.downloaded_at
                >= datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
            )
            .group_by(day_col)
            .order_by(day_col)
        ).all()

        by_day: dict[date, tuple[int, int]] = {}
        for row in rows:
            day = (
                row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0]))
            )
            by_day[day] = (int(row[1] or 0), int(row[2] or 0))

        timeline: list[DownloadTimelinePoint] = []
        for offset in range(days):
            day = start + timedelta(days=offset)
            count, size_bytes = by_day.get(day, (0, 0))
            timeline.append(
                DownloadTimelinePoint(
                    date=day.isoformat(), count=count, size_bytes=size_bytes
                )
            )
        return timeline

    @begin_session
    def prune_events_older_than(
        self,
        cutoff: datetime,
        session: Session = None,  # type: ignore
    ) -> int:
        """Delete log rows older than `cutoff`, returning how many went.

        Deliberately does not touch `roms.download_count`, that is a lifetime
        total, and an admin pruning the audit log shouldn't silently rewrite
        history on the game pages.
        """
        result = session.execute(
            delete(DownloadEvent)
            .where(DownloadEvent.downloaded_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0

    @begin_session
    def get_rom_download_count(
        self,
        rom_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(DownloadEvent)
                .where(DownloadEvent.rom_id == rom_id)
            )
            or 0
        )

    @begin_session
    def resync_rom_counters(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        """Rebuild `roms.download_count` / `last_downloaded_at` from the event log.

        A repair path for counters that drifted (restored backup, manual edits).
        Returns the number of roms with a non-zero count afterwards.

        Note the interaction with retention: this rebuilds from the rows that
        are still *present*, so running it after the log has been pruned lowers
        every counter to the retained window. Only use it when the counters are
        actually wrong.
        """
        counts_sq = (
            select(
                DownloadEvent.rom_id.label("rom_id"),
                func.count(DownloadEvent.id).label("download_count"),
                func.max(DownloadEvent.downloaded_at).label("last_downloaded_at"),
            )
            .where(DownloadEvent.rom_id.is_not(None))
            .group_by(DownloadEvent.rom_id)
            .subquery()
        )

        session.execute(
            update(Rom)
            .values(
                download_count=func.coalesce(
                    select(counts_sq.c.download_count)
                    .where(counts_sq.c.rom_id == Rom.id)
                    .scalar_subquery(),
                    0,
                ),
                last_downloaded_at=select(counts_sq.c.last_downloaded_at)
                .where(counts_sq.c.rom_id == Rom.id)
                .scalar_subquery(),
            )
            .execution_options(synchronize_session=False)
        )

        return (
            session.scalar(
                select(func.count()).select_from(Rom).where(Rom.download_count > 0)
            )
            or 0
        )
