from datetime import datetime
from typing import Literal

from sqlalchemy import TIMESTAMP, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import BaseModel

# The only two decisions: the container's pre-existing card was imported, or
# it was wiped. The single source of truth for both the column and its writers.
AdoptionOutcome = Literal["adopt", "discard"]


class StreamingContainerAdoption(BaseModel):
    """One row per streaming container, recording the one-time decision about
    the card that was already on it when memory_card_sync was enabled.

    Keyed by container rather than by card: a card can be deleted, and if the
    marker went with it the next user would be offered a container card that by
    then holds someone else's saves.
    """

    __tablename__ = "streaming_container_adoptions"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    container_key: Mapped[str] = mapped_column(String(length=512), unique=True)
    outcome: Mapped[AdoptionOutcome] = mapped_column(String(length=16))
    decided_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
