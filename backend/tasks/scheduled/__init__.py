from dataclasses import dataclass

from tasks.tasks import update_job_meta


@dataclass
class UpdateStats:
    """Statistics for LaunchBox metadata update operations."""

    processed: int = 0
    total: int = 0

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        update_job_meta({"update_stats": self.to_dict()})

    def to_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "total": self.total,
        }
