import uuid
from dataclasses import dataclass
from typing import Self

from models.channel import Channel
from models.rom import RomFile


@dataclass(frozen=True)
class FileKey:
    """The ROM file a channel belongs to: its SHA-1, or its name and size when unhashed."""

    sha1: str | None
    name: str
    size: int

    @classmethod
    def of_file(cls, rom_file: RomFile) -> Self:
        return cls(
            sha1=rom_file.sha1_hash or None,
            name=rom_file.file_name,
            size=rom_file.file_size_bytes,
        )

    @classmethod
    def of_channel(cls, channel: Channel) -> Self:
        return cls(
            sha1=channel.target_file_hash,
            name=channel.target_file_name,
            size=channel.target_file_size,
        )

    def matches(self, other: "FileKey") -> bool:
        # A channel keyed by name before its file was hashed still matches that file.
        if self.sha1 and other.sha1:
            return self.sha1 == other.sha1
        return (self.name, self.size) == (other.name, other.size)

    def channel_columns(self) -> dict[str, str | int | None]:
        return {
            "target_file_hash": self.sha1,
            "target_file_name": self.name,
            "target_file_size": self.size,
        }

    def new_channel(
        self,
        user_id: int,
        rom_id: int,
        platform_id: int,
        label: str,
        id: uuid.UUID | None = None,
    ) -> Channel:
        """A channel keyed to this file, not yet added to a session.

        Args:
            id: the id a client chose for it, else a generated one.
        """
        channel = Channel(
            user_id=user_id,
            rom_id=rom_id,
            platform_id=platform_id,
            label=label,
            **self.channel_columns(),
        )
        if id is not None:
            channel.id = id
        return channel
