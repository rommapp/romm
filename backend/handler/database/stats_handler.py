from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute

from decorators.database import begin_session
from models.assets import Save, Screenshot, State
from models.rom import Rom, RomFile

from .base_handler import DBBaseHandler


class DBStatsHandler(DBBaseHandler):
    @begin_session
    def get_platforms_count(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        """Get the number of platforms with any roms."""
        return (
            session.scalar(
                select(func.count(distinct(Rom.platform_id))).select_from(Rom)
            )
            or 0
        )

    @begin_session
    def get_roms_count(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        return session.scalar(select(func.count()).select_from(Rom)) or 0

    @begin_session
    def get_saves_count(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        return session.scalar(select(func.count()).select_from(Save)) or 0

    @begin_session
    def get_states_count(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        return session.scalar(select(func.count()).select_from(State)) or 0

    @begin_session
    def get_screenshots_count(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        return session.scalar(select(func.count()).select_from(Screenshot)) or 0

    @begin_session
    def get_total_filesize(
        self,
        session: Session = None,  # type: ignore
    ) -> int:
        """Get the total filesize of all roms in the database, in bytes."""
        return (
            session.scalar(
                select(func.sum(RomFile.file_size_bytes)).select_from(RomFile)
            )
            or 0
        )

    @begin_session
    def get_platform_filesize(
        self,
        platform_id: int,
        session: Session = None,  # type: ignore
    ) -> int:
        """Get the total filesize of all roms in the database, in bytes."""
        return (
            session.scalar(
                select(func.sum(RomFile.file_size_bytes))
                .select_from(RomFile)
                .join(Rom)
                .filter(Rom.platform_id == platform_id)
            )
            or 0
        )

    # Metadata source columns on the Rom model, keyed by source identifier.
    METADATA_SOURCE_COLUMNS: dict[str, "InstrumentedAttribute"] = {
        "igdb": Rom.igdb_id,
        "ss": Rom.ss_id,
        "moby": Rom.moby_id,
        "launchbox": Rom.launchbox_id,
        "ra": Rom.ra_id,
        "hasheous": Rom.hasheous_id,
        "tgdb": Rom.tgdb_id,
        "flashpoint": Rom.flashpoint_id,
        "hltb": Rom.hltb_id,
        "gamelist": Rom.gamelist_id,
    }

    @begin_session
    def get_metadata_coverage_by_platform(
        self,
        session: Session = None,  # type: ignore
    ) -> dict[int, list[dict]]:
        """Get the count of ROMs matched per metadata source, grouped by platform."""
        rows = session.execute(
            select(
                Rom.platform_id,
                *(
                    func.count(col).label(key)
                    for key, col in self.METADATA_SOURCE_COLUMNS.items()
                ),
            )
            .select_from(Rom)
            .group_by(Rom.platform_id)
        ).all()

        result: dict[int, list[dict]] = {}
        for row in rows:
            result[row.platform_id] = [
                {"source": key, "matched": getattr(row, key)}
                for key in self.METADATA_SOURCE_COLUMNS
                if getattr(row, key) > 0
            ]
        return result

    @begin_session
    def get_region_breakdown_by_platform(
        self,
        session: Session = None,  # type: ignore
    ) -> dict[int, list[dict]]:
        """Get the count of ROMs per region, grouped by platform."""
        rows = session.execute(
            select(Rom.platform_id, Rom.regions).where(
                Rom.regions.is_not(None)
            )
        ).all()

        counter: dict[int, dict[str, int]] = {}
        for platform_id, regions_list in rows:
            if regions_list:
                if platform_id not in counter:
                    counter[platform_id] = {}
                for region in regions_list:
                    counter[platform_id][region] = (
                        counter[platform_id].get(region, 0) + 1
                    )

        return {
            pid: [
                {"region": r, "count": c}
                for r, c in sorted(regions.items(), key=lambda x: -x[1])
            ]
            for pid, regions in counter.items()
        }
