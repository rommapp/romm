"""The ROM visibility rule a caller's queries and loaded-ROM checks share.

Built from ``ResolvedPermissions.rom_visibility`` and handed to the database
handlers, so a new restriction lands in one place instead of in every query
that filters ROMs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Protocol

from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from models.rom import Rom


class VisibilityColumns(Protocol):
    """The ROM columns `RomVisibilityFilter.allows` reads."""

    @property
    def id(self) -> int: ...

    @property
    def platform_id(self) -> int: ...


@dataclass(frozen=True)
class RomVisibilityFilter:
    """Which ROMs a caller may see: none on a hidden platform, none hidden directly."""

    hidden_platform_ids: frozenset[int] = frozenset()
    hidden_rom_ids: frozenset[int] = frozenset()

    @property
    def is_unrestricted(self) -> bool:
        return not (self.hidden_platform_ids or self.hidden_rom_ids)

    def clauses(
        self,
        *,
        rom_id_col: InstrumentedAttribute[int] = Rom.id,
        platform_id_col: InstrumentedAttribute[int] = Rom.platform_id,
    ) -> list[ColumnElement[bool]]:
        """WHERE clauses keeping only visible ROMs; empty when nothing is hidden.

        The columns are overridable so a query on the `roms_facets` mirror
        filters on its own columns instead of joining `roms`.
        """
        clauses: list[ColumnElement[bool]] = []
        if self.hidden_platform_ids:
            clauses.append(platform_id_col.not_in(self.hidden_platform_ids))
        if self.hidden_rom_ids:
            clauses.append(rom_id_col.not_in(self.hidden_rom_ids))
        return clauses

    def allows(self, rom: VisibilityColumns) -> bool:
        return (
            rom.platform_id not in self.hidden_platform_ids
            and rom.id not in self.hidden_rom_ids
        )


UNRESTRICTED: Final = RomVisibilityFilter()
