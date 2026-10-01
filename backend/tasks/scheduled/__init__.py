from dataclasses import dataclass
from typing import ClassVar

from tasks.tasks import JobMetaStats


@dataclass
class UpdateStats(JobMetaStats):
    """Statistics for LaunchBox metadata update operations."""

    meta_key: ClassVar[str] = "update_stats"

    processed: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "total": self.total,
        }
