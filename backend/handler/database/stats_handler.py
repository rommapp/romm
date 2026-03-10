from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

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

    @begin_session
    def get_metadata_coverage_by_platform(
        self,
        session: Session = None,  # type: ignore
    ) -> dict[int, list[dict]]:
        """Get the count of ROMs matched per metadata source, grouped by platform."""
        source_keys = [
            "igdb", "ss", "moby", "launchbox", "ra",
            "hasheous", "tgdb", "flashpoint", "hltb", "gamelist",
        ]

        rows = session.execute(
            select(
                Rom.platform_id,
                func.count(Rom.igdb_id).label("igdb"),
                func.count(Rom.ss_id).label("ss"),
                func.count(Rom.moby_id).label("moby"),
                func.count(Rom.launchbox_id).label("launchbox"),
                func.count(Rom.ra_id).label("ra"),
                func.count(Rom.hasheous_id).label("hasheous"),
                func.count(Rom.tgdb_id).label("tgdb"),
                func.count(Rom.flashpoint_id).label("flashpoint"),
                func.count(Rom.hltb_id).label("hltb"),
                func.count(Rom.gamelist_id).label("gamelist"),
            )
            .select_from(Rom)
            .group_by(Rom.platform_id)
        ).all()

        result: dict[int, list[dict]] = {}
        for row in rows:
            result[row.platform_id] = [
                {"source": key, "matched": getattr(row, key)}
                for key in source_keys
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
