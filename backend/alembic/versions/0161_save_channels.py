"""Add channels, snapshots and their bank, the content columns they need, and
the per-file identity sigil reads for a restore, then file every slotted save
under a channel named after its slot.

Revision ID: 0161_save_channels
Revises: 0160_state_origin_device
Create Date: 2026-10-05 00:00:00.000000

"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from handler.snapshots.legacy import channel_label, sync_file
from models.rom import RomFile, RomFileCategory
from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0161_save_channels"
down_revision = "0160_state_origin_device"
branch_labels = None
depends_on = None

# Frozen copies of the model enums, so a fresh install creates these exact types.
ENUMS = {
    "saveshape": ("SINGLE", "MULTI", "FOLDER"),
    "saveformat": ("NEUTRAL", "NATIVE"),
    "snapshotkind": ("CHANNEL", "ARCHIVAL", "BRANCH"),
}

CURRENT_SNAPSHOT_FK = "fk_channels_current_snapshot_id"
SCREENSHOT_LINKS = ("save_id", "state_id")
# Each content table's channel link and the index it is listed through.
CHANNEL_CONTENT = {
    "saves": ("ix_saves_channel_updated", ("channel_id", "updated_at")),
    "states": ("ix_states_channel_id", ("channel_id",)),
}


def _enum(name: str) -> sa.types.TypeEngine[str]:
    """The PostgreSQL type created up front, which the other engines inline."""
    if is_postgresql(op.get_bind()):
        return ENUM(*ENUMS[name], name=name, create_type=False)
    return sa.Enum(*ENUMS[name], name=name)


def _timestamps() -> list[sa.Column[datetime]]:
    return [
        sa.Column(
            column,
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        )
        for column in ("created_at", "updated_at")
    ]


def _flag(name: str) -> sa.Column[bool]:
    return sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false())


def _foreign_keys(table: str) -> set[str | None]:
    # No `if_not_exists` on `create_foreign_key`, so existing ones are reflected.
    return {key["name"] for key in sa.inspect(op.get_bind()).get_foreign_keys(table)}


def _relink_rom(table: str, ondelete: str, nullable: bool) -> None:
    """Point `table.rom_id` at roms with `ondelete`, replacing whatever key it had."""
    inspector = sa.inspect(op.get_bind())
    keys = [
        key
        for key in inspector.get_foreign_keys(table)
        if key["constrained_columns"] == ["rom_id"]
    ]
    column = next(c for c in inspector.get_columns(table) if c["name"] == "rom_id")
    if (
        len(keys) == 1
        and (keys[0].get("options") or {}).get("ondelete", "").upper() == ondelete
        and column["nullable"] == nullable
    ):
        return
    for key in keys:
        op.drop_constraint(key["name"], table, type_="foreignkey")
    op.alter_column(table, "rom_id", existing_type=sa.Integer(), nullable=nullable)
    op.create_foreign_key(
        f"fk_{table}_rom_id", table, "roms", ["rom_id"], ["id"], ondelete=ondelete
    )


def _add_channels() -> None:
    conn = op.get_bind()
    if is_postgresql(conn):
        for name, values in ENUMS.items():
            ENUM(*values, name=name).create(conn, checkfirst=True)

    op.create_table(
        "channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=True),
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("target_file_hash", sa.String(length=100), nullable=True),
        sa.Column("target_file_name", sa.String(length=450), nullable=False),
        sa.Column("target_file_size", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("current_snapshot_id", sa.Integer(), nullable=True),
        _flag("is_hardcore"),
        _flag("is_public"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("channels") as batch_op:
        batch_op.create_index(
            "ix_channels_user_rom", ["user_id", "rom_id"], if_not_exists=True
        )
        batch_op.create_index("ix_channels_rom_id", ["rom_id"], if_not_exists=True)
        batch_op.create_index(
            "ix_channels_platform_file_hash",
            ["platform_id", "target_file_hash"],
            if_not_exists=True,
        )
        batch_op.create_index(
            "ix_channels_platform_file_name",
            ["platform_id", "target_file_name", "target_file_size"],
            if_not_exists=True,
        )
        batch_op.create_index(
            "ix_channels_current_snapshot_id",
            ["current_snapshot_id"],
            if_not_exists=True,
        )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("rom_id", sa.Integer(), nullable=True),
        sa.Column("channel_id", sa.Uuid(), nullable=True),
        sa.Column("parent_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("kind", _enum("snapshotkind"), nullable=False),
        _flag("is_public"),
        sa.Column("save_id", sa.Integer(), nullable=True),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("rom_sha1", sa.String(length=100), nullable=True),
        _flag("is_hardcore"),
        sa.Column("save_target", sa.String(length=100), nullable=True),
        sa.Column("emulator", sa.String(length=50), nullable=True),
        sa.Column("origin_device_id", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_snapshot_id"], ["snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["save_id"], ["saves.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["origin_device_id"], ["devices.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("snapshots") as batch_op:
        for name, columns in (
            ("ix_snapshots_channel_created", ["channel_id", "created_at"]),
            ("ix_snapshots_channel_digest", ["channel_id", "digest"]),
            ("ix_snapshots_user_rom_kind", ["user_id", "rom_id", "kind"]),
            ("ix_snapshots_author_user_id", ["author_user_id"]),
            ("ix_snapshots_rom_id", ["rom_id"]),
            ("ix_snapshots_parent_snapshot_id", ["parent_snapshot_id"]),
            ("ix_snapshots_save_id", ["save_id"]),
            ("ix_snapshots_origin_device_id", ["origin_device_id"]),
        ):
            batch_op.create_index(name, columns, if_not_exists=True)

    if CURRENT_SNAPSHOT_FK not in _foreign_keys("channels"):
        op.create_foreign_key(
            CURRENT_SNAPSHOT_FK,
            "channels",
            "snapshots",
            ["current_snapshot_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "snapshot_states",
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("core", sa.String(length=50), nullable=False),
        sa.Column("slot", sa.String(length=50), nullable=False),
        sa.Column("state_id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["state_id"], ["states.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("snapshot_id", "core", "slot"),
        if_not_exists=True,
    )
    with op.batch_alter_table("snapshot_states") as batch_op:
        batch_op.create_index(
            "ix_snapshot_states_state_id", ["state_id"], if_not_exists=True
        )

    op.create_table(
        "snapshot_pins",
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_id", "user_id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("snapshot_pins") as batch_op:
        batch_op.create_index(
            "ix_snapshot_pins_user_id", ["user_id"], if_not_exists=True
        )

    op.create_table(
        "device_channel_sync",
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("base_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("latest_known_id", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["base_snapshot_id"], ["snapshots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["latest_known_id"], ["snapshots.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("device_id", "channel_id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("device_channel_sync") as batch_op:
        batch_op.create_index(
            "ix_device_channel_sync_channel_id", ["channel_id"], if_not_exists=True
        )
        batch_op.create_index(
            "ix_device_channel_sync_base_snapshot_id",
            ["base_snapshot_id"],
            if_not_exists=True,
        )
        batch_op.create_index(
            "ix_device_channel_sync_latest_known_id",
            ["latest_known_id"],
            if_not_exists=True,
        )

    with op.batch_alter_table("saves") as batch_op:
        batch_op.add_column(
            sa.Column("identity_hash", sa.String(length=32), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("shape", _enum("saveshape"), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("format", _enum("saveformat"), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("emulator_version", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("core", sa.String(length=50), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("core_version", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )

    with op.batch_alter_table("states") as batch_op:
        batch_op.add_column(
            sa.Column("emulator_version", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("core_version", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )

    for table, index in CHANNEL_CONTENT.items():
        # Deleting a ROM detaches its saves and states instead of taking them along.
        _relink_rom(table, "SET NULL", nullable=True)
        keys = _foreign_keys(table)
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("channel_id", sa.Uuid(), nullable=True), if_not_exists=True
            )
            batch_op.create_index(index[0], list(index[1]), if_not_exists=True)
            if f"fk_{table}_channel_id" not in keys:
                batch_op.create_foreign_key(
                    f"fk_{table}_channel_id",
                    "channels",
                    ["channel_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    screenshot_keys = _foreign_keys("screenshots")
    with op.batch_alter_table("screenshots") as batch_op:
        for column in SCREENSHOT_LINKS:
            batch_op.add_column(
                sa.Column(column, sa.Integer(), nullable=True), if_not_exists=True
            )
            batch_op.create_index(
                f"ix_screenshots_{column}", [column], unique=True, if_not_exists=True
            )
            if f"fk_screenshots_{column}" not in screenshot_keys:
                batch_op.create_foreign_key(
                    f"fk_screenshots_{column}",
                    f"{column.removesuffix('_id')}s",
                    [column],
                    ["id"],
                    ondelete="CASCADE",
                )


def _drop_channels() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    screenshot_keys = _foreign_keys("screenshots")
    screenshot_indexes = {
        index["name"] for index in inspector.get_indexes("screenshots")
    }
    with op.batch_alter_table("screenshots") as batch_op:
        # MariaDB refuses to drop an index a foreign key still sits on.
        for column in SCREENSHOT_LINKS:
            if f"fk_screenshots_{column}" in screenshot_keys:
                batch_op.drop_constraint(f"fk_screenshots_{column}", type_="foreignkey")
            if f"ix_screenshots_{column}" in screenshot_indexes:
                batch_op.drop_index(f"ix_screenshots_{column}")
            batch_op.drop_column(column, if_exists=True)

    for table, index in CHANNEL_CONTENT.items():
        keys = _foreign_keys(table)
        indexes = {i["name"] for i in inspector.get_indexes(table)}
        with op.batch_alter_table(table) as batch_op:
            if f"fk_{table}_channel_id" in keys:
                batch_op.drop_constraint(f"fk_{table}_channel_id", type_="foreignkey")
            if index[0] in indexes:
                batch_op.drop_index(index[0])
            batch_op.drop_column("channel_id", if_exists=True)

    with op.batch_alter_table("states") as batch_op:
        batch_op.drop_column("core_version", if_exists=True)
        batch_op.drop_column("emulator_version", if_exists=True)

    with op.batch_alter_table("saves") as batch_op:
        batch_op.drop_column("core_version", if_exists=True)
        batch_op.drop_column("core", if_exists=True)
        batch_op.drop_column("emulator_version", if_exists=True)
        batch_op.drop_column("format", if_exists=True)
        batch_op.drop_column("shape", if_exists=True)
        batch_op.drop_column("identity_hash", if_exists=True)

    # channels and snapshots point at each other, so one side lets go first.
    if inspector.has_table("channels") and CURRENT_SNAPSHOT_FK in _foreign_keys(
        "channels"
    ):
        op.drop_constraint(CURRENT_SNAPSHOT_FK, "channels", type_="foreignkey")
    for table in (
        "device_channel_sync",
        "snapshot_pins",
        "snapshot_states",
        "snapshots",
        "channels",
    ):
        op.drop_table(table, if_exists=True)

    for table in CHANNEL_CONTENT:
        # Before this revision a ROM's deletion took these rows with it.
        op.execute(sa.text(f"DELETE FROM {table} WHERE rom_id IS NULL"))  # nosec B608
        _relink_rom(table, "CASCADE", nullable=False)

    if is_postgresql(conn):
        for name, values in ENUMS.items():
            ENUM(*values, name=name).drop(conn, checkfirst=True)


def _sigil_identity_columns() -> list[sa.Column]:
    return [
        sa.Column("raw_serial", sa.String(length=100), nullable=True),
        sa.Column("sigil_features", sa.BigInteger(), nullable=True),
        sa.Column("n64_header", sa.String(length=100), nullable=True),
        sa.Column("n64_md5", sa.String(length=100), nullable=True),
        sa.Column("n64_md5_n64", sa.String(length=100), nullable=True),
        sa.Column("playlist_title_ids", CustomJSON(), nullable=True),
    ]


def _add_sigil_identity() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in _sigil_identity_columns():
            batch_op.add_column(column, if_not_exists=True)


def _drop_sigil_identity() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in reversed(_sigil_identity_columns()):
            batch_op.drop_column(column.name, if_exists=True)


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


def _link_slots_to_channels() -> None:
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


def upgrade() -> None:
    _add_channels()
    _add_sigil_identity()
    _link_slots_to_channels()


def downgrade() -> None:
    # Dropping the channels unlinks the saves filed under them.
    _drop_sigil_identity()
    _drop_channels()
