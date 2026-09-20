from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel
from utils.database import CustomJSON

if TYPE_CHECKING:
    from models.rom import Rom


class RomSimilarity(BaseModel):
    """A precomputed edge of the item-item similarity graph.

    Written wholesale by the recommendations task so the rows are consistent
    with a single IDF snapshot of the library, and only the top neighbours of
    each ROM are kept.

    Edges are stored in both directions: the scoring is symmetric but the
    per-ROM top-N cut is not, and duplicating avoids an OR across two indexed
    columns on every read.
    """

    __tablename__ = "rom_similarity"

    __table_args__ = (
        Index("idx_rom_similarity_rom_score", "rom_id", "score"),
        Index("idx_rom_similarity_related_rom_id", "related_rom_id"),
    )

    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), primary_key=True
    )
    related_rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), primary_key=True
    )

    score: Mapped[float] = mapped_column(Float(), nullable=False)

    # The facets that drove the score, e.g. [{"facet": "franchise",
    # "value": "Metroid"}], so the UI can say why without recomputing.
    reasons: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CustomJSON(), default=[]
    )

    # No ORM-level delete cascade: ROMs are removed with a bulk `delete()`,
    # so the foreign keys' ON DELETE CASCADE is what clears both directions.
    rom: Mapped[Rom] = relationship(
        "Rom",
        foreign_keys=[rom_id],
        back_populates="similar_roms",
        lazy="raise",
        passive_deletes=True,
    )
    related_rom: Mapped[Rom] = relationship(
        "Rom", foreign_keys=[related_rom_id], lazy="raise", passive_deletes=True
    )
