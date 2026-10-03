"""The ROM visibility rule a caller's queries and loaded-ROM checks share."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Final, Protocol

from sqlalchemy import and_, not_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from models.rom import Rom


class VisibilityColumns(Protocol):
    """The ROM columns `RomVisibilityFilter.allows` reads."""

    @property
    def id(self) -> int: ...

    @property
    def platform_id(self) -> int: ...


def _always_visible(rom: VisibilityColumns) -> bool:
    return True


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
        """WHERE clauses keeping only visible ROMs, on columns a query on the
        `roms_facets` mirror overrides to skip a join to `roms`."""
        clauses = self._row_clauses(platform_id_col)
        if self.hidden_rom_ids:
            clauses.append(rom_id_col.not_in(self.hidden_rom_ids))
        return clauses

    def row_hidden_clause(self) -> ColumnElement[bool] | None:
        """WHERE clause matching the `roms` rows a rule other than a direct hide
        keeps out, or None when no such rule applies."""
        clauses = self._row_clauses(Rom.platform_id)
        return not_(and_(*clauses)) if clauses else None

    def _row_clauses(
        self, platform_id_col: InstrumentedAttribute[int]
    ) -> list[ColumnElement[bool]]:
        """The rules decided by a ROM's row rather than by its id alone."""
        clauses: list[ColumnElement[bool]] = []
        if self.hidden_platform_ids:
            clauses.append(platform_id_col.not_in(self.hidden_platform_ids))
        return clauses

    @cached_property
    def allows(self) -> Callable[[VisibilityColumns], bool]:
        """Whether a loaded ROM is visible, picked once so a per-ROM loop pays one call."""
        return _always_visible if self.is_unrestricted else self._allows

    def _allows(self, rom: VisibilityColumns) -> bool:
        return (
            rom.platform_id not in self.hidden_platform_ids
            and rom.id not in self.hidden_rom_ids
        )


UNRESTRICTED: Final = RomVisibilityFilter()
