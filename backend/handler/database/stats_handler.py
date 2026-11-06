from __future__ import annotations

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from endpoints.responses.stats import MetadataCoverageItem, RegionBreakdownItem
from handler.auth.rom_visibility import UNRESTRICTED, RomVisibilityFilter
from models.assets import RomAsset, Save, Screenshot, State
from models.rom import (
    METADATA_SOURCE_FACET_COLUMNS,
    Rom,
    RomFacets,
    RomFile,
)
from utils.database import is_non_blank

from .base_handler import DBBaseHandler


class DBStatsHandler(DBBaseHandler):
    @begin_session
    def get_platforms_count(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> int:
        """Get the number of platforms with any roms."""
        query = (
            select(func.count(distinct(Rom.platform_id)))
            .select_from(Rom)
            .where(*visibility.clauses())
        )
        return session.scalar(query) or 0

    @begin_session
    def get_roms_count(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> int:
        query = select(func.count()).select_from(Rom).where(*visibility.clauses())
        return session.scalar(query) or 0

    @staticmethod
    def _asset_count(
        session: Session, model: type[RomAsset], visibility: RomVisibilityFilter
    ) -> int:
        """Count every user's `model` rows whose ROM `visibility` keeps."""
        query = select(func.count()).select_from(model)
        if not visibility.is_unrestricted:
            query = query.join(RomFacets, RomFacets.rom_id == model.rom_id).where(
                *visibility.facets_clauses()
            )
        return session.scalar(query) or 0

    @begin_session
    def get_saves_count(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> int:
        return self._asset_count(session, Save, visibility)

    @begin_session
    def get_states_count(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> int:
        return self._asset_count(session, State, visibility)

    @begin_session
    def get_screenshots_count(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> int:
        return self._asset_count(session, Screenshot, visibility)

    @begin_session
    def get_total_filesize(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> int:
        """Get the total filesize of all roms in the database, in bytes."""
        query = select(func.sum(RomFile.file_size_bytes)).select_from(RomFile)
        if not visibility.is_unrestricted:
            query = query.join(Rom).where(*visibility.clauses())
        return session.scalar(query) or 0

    @begin_session
    def get_metadata_coverage_by_platform(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> dict[int, list[MetadataCoverageItem]]:
        """Get the count of ROMs matched per metadata source, grouped by platform.

        Aggregates the narrow `roms_facets` mirror instead of `roms`, whose rows
        also carry the raw provider-metadata blobs.
        """
        rows = session.execute(
            select(
                RomFacets.platform_id,
                *(
                    func.count(case((is_non_blank(col), 1))).label(key)
                    for key, col in METADATA_SOURCE_FACET_COLUMNS.items()
                ),
            )
            .select_from(RomFacets)
            .where(*visibility.facets_clauses())
            .group_by(RomFacets.platform_id)
        ).all()

        result: dict[int, list[MetadataCoverageItem]] = {}
        for row in rows:
            result[row.platform_id] = [
                MetadataCoverageItem(source=key, matched=getattr(row, key))
                for key in METADATA_SOURCE_FACET_COLUMNS
                if getattr(row, key) > 0
            ]

        return result

    @begin_session
    def get_region_breakdown_by_platform(
        self,
        visibility: RomVisibilityFilter = UNRESTRICTED,
        session: Session = INJECTED_SESSION,
    ) -> dict[int, list[RegionBreakdownItem]]:
        """Get the count of ROMs per region, grouped by platform.

        Reads the narrow `roms_facets` mirror rather than scanning `roms`.
        """
        rows = session.execute(
            select(RomFacets.platform_id, RomFacets.regions).where(
                RomFacets.regions.is_not(None), *visibility.facets_clauses()
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
