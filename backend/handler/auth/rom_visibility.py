"""The ROM visibility rule a caller's queries and loaded-ROM checks share."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Final, Protocol

from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from models.rom import Rom


class VisibilityColumns(Protocol):
    """The ROM columns `RomVisibilityFilter.allows` reads."""

    @property
    def id(self) -> int: ...

    @property
    def platform_id(self) -> int: ...

    @property
    def min_age(self) -> int | None: ...


def _always_visible(rom: VisibilityColumns) -> bool:
    return True


@dataclass(frozen=True)
class RomVisibilityFilter:
    """Which ROMs a caller may see: none on a hidden platform, none hidden
    directly, and none rated above the age limit unless exempt."""

    hidden_platform_ids: frozenset[int] = frozenset()
    hidden_rom_ids: frozenset[int] = frozenset()
    age_limit: int | None = None
    # Whether a ROM no rating covers is hidden while an age rule applies.
    hide_unrated_roms: bool = False
    # ROMs the age rule lets through; an explicit hide still applies to them.
    age_exempt_rom_ids: frozenset[int] = frozenset()

    @property
    def has_age_rule(self) -> bool:
        return self.age_limit is not None or self.hide_unrated_roms

    @property
    def is_unrestricted(self) -> bool:
        return not (self.hidden_platform_ids or self.hidden_rom_ids) and (
            not self.has_age_rule
        )

    def clauses(
        self,
        *,
        rom_id_col: InstrumentedAttribute[int] = Rom.id,
        platform_id_col: InstrumentedAttribute[int] = Rom.platform_id,
        min_age_col: InstrumentedAttribute[int | None] = Rom.min_age,
    ) -> list[ColumnElement[bool]]:
        """WHERE clauses keeping only visible ROMs, on columns a query on the
        `roms_facets` mirror overrides to skip a join to `roms`."""
        clauses = self._row_clauses(rom_id_col, platform_id_col, min_age_col)
        if self.hidden_rom_ids:
            clauses.append(rom_id_col.not_in(self.hidden_rom_ids))
        return clauses

    def row_hidden_clause(self) -> ColumnElement[bool] | None:
        """WHERE clause matching the `roms` rows a rule other than a direct hide
        keeps out, or None when no such rule applies."""
        clauses = self._row_clauses(Rom.id, Rom.platform_id, Rom.min_age)
        return not_(and_(*clauses)) if clauses else None

    def _row_clauses(
        self,
        rom_id_col: InstrumentedAttribute[int],
        platform_id_col: InstrumentedAttribute[int],
        min_age_col: InstrumentedAttribute[int | None],
    ) -> list[ColumnElement[bool]]:
        """The rules decided by a ROM's row rather than by its id alone, each true
        or false and never NULL so `row_hidden_clause` can negate it."""
        clauses: list[ColumnElement[bool]] = []
        if self.hidden_platform_ids:
            clauses.append(platform_id_col.not_in(self.hidden_platform_ids))
        if self.has_age_rule:
            clauses.append(self._age_clause(rom_id_col, min_age_col))
        return clauses

    def _age_clause(
        self,
        rom_id_col: InstrumentedAttribute[int],
        min_age_col: InstrumentedAttribute[int | None],
    ) -> ColumnElement[bool]:
        allowed: list[ColumnElement[bool]]
        if self.age_limit is None:
            allowed = [min_age_col.is_not(None)]
        elif self.hide_unrated_roms:
            allowed = [and_(min_age_col.is_not(None), min_age_col <= self.age_limit)]
        else:
            allowed = [min_age_col.is_(None), min_age_col <= self.age_limit]
        if self.age_exempt_rom_ids:
            allowed.append(rom_id_col.in_(self.age_exempt_rom_ids))
        return or_(*allowed)

    @cached_property
    def allows(self) -> Callable[[VisibilityColumns], bool]:
        """Whether a loaded ROM is visible, picked once so a per-ROM loop pays one call."""
        if self.is_unrestricted:
            return _always_visible
        return self._allows_with_age if self.has_age_rule else self._allows

    def _allows(self, rom: VisibilityColumns) -> bool:
        return (
            rom.platform_id not in self.hidden_platform_ids
            and rom.id not in self.hidden_rom_ids
        )

    def _allows_with_age(self, rom: VisibilityColumns) -> bool:
        if not self._allows(rom):
            return False
        min_age = rom.min_age
        if min_age is None:
            rated_ok = not self.hide_unrated_roms
        else:
            rated_ok = self.age_limit is None or min_age <= self.age_limit
        return rated_ok or rom.id in self.age_exempt_rom_ids


UNRESTRICTED: Final = RomVisibilityFilter()
