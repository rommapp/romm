"""File every slotted save under a channel named after its slot.

Revision ID: 0153_link_slots_to_channels
Revises: 0152_save_channels
Create Date: 2026-10-05 00:00:00.000000

"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

from handler.snapshots.legacy import channel_label, sync_file
from models.rom import RomFile, RomFileCategory

# revision identifiers, used by Alembic.
revision = "0153_link_slots_to_channels"
down_revision = "0152_save_channels"
branch_labels = None
depends_on = None


def _rom_files(conn: sa.Connection, rom_id: int) -> list[RomFile]:
    rows = conn.execute(
        sa.text(
            "SELECT file_name, file_size_bytes, sha1_hash, category, missing_from_fs "
            "FROM rom_files WHERE rom_id = :rom_id"
        ),
        {"rom_id": rom_id},
    )
    return [
        RomFile(
            file_name=row.file_name,
            file_size_bytes=row.file_size_bytes,
            sha1_hash=row.sha1_hash,
            category=RomFileCategory[row.category] if row.category else None,
            missing_from_fs=bool(row.missing_from_fs),
        )
        for row in rows
    ]


def upgrade() -> None:
    conn = op.get_bind()
    # Only saves not yet linked, so a run that died partway resumes.
    groups = conn.execute(
        sa.text(
            "SELECT DISTINCT s.user_id, s.rom_id, s.slot, r.platform_id "
            "FROM saves s JOIN roms r ON r.id = s.rom_id "
            "WHERE s.slot IS NOT NULL AND s.channel_id IS NULL"
        )
    ).all()

    channels: dict[tuple[int, int, str], uuid.UUID] = {}
    for user_id, rom_id, slot, platform_id in groups:
        label = channel_label(slot)
        rom_file = sync_file(_rom_files(conn, rom_id))
        if label is None or rom_file is None:
            continue
        key = (user_id, rom_id, label.lower())
        channel_id = (
            channels.get(key)
            or conn.execute(
                sa.text(
                    "SELECT id FROM channels WHERE user_id = :user_id "
                    "AND rom_id = :rom_id AND LOWER(label) = LOWER(:label) "
                    "ORDER BY created_at"
                ),
                {"user_id": user_id, "rom_id": rom_id, "label": label},
            ).scalar()
        )
        if channel_id is None:
            channel_id = uuid.uuid7()
            now = datetime.now(timezone.utc)
            conn.execute(
                sa.insert(
                    sa.table(
                        "channels",
                        sa.column("id", sa.Uuid()),
                        sa.column("user_id"),
                        sa.column("rom_id"),
                        sa.column("platform_id"),
                        sa.column("target_file_hash"),
                        sa.column("target_file_name"),
                        sa.column("target_file_size"),
                        sa.column("label"),
                        sa.column("created_at"),
                        sa.column("updated_at"),
                    )
                ).values(
                    id=channel_id,
                    user_id=user_id,
                    rom_id=rom_id,
                    platform_id=platform_id,
                    target_file_hash=rom_file.sha1_hash or None,
                    target_file_name=rom_file.file_name,
                    target_file_size=rom_file.file_size_bytes,
                    label=label,
                    created_at=now,
                    updated_at=now,
                )
            )
        channels[key] = uuid.UUID(str(channel_id))
        conn.execute(
            sa.update(
                sa.table(
                    "saves",
                    sa.column("user_id"),
                    sa.column("rom_id"),
                    sa.column("slot"),
                    sa.column("channel_id", sa.Uuid()),
                )
            )
            .where(
                sa.column("user_id") == user_id,
                sa.column("rom_id") == rom_id,
                sa.column("slot") == slot,
                sa.column("channel_id").is_(None),
            )
            .values(channel_id=channels[key])
        )


def downgrade() -> None:
    # 0152's downgrade drops the column and the channels with it.
    pass
