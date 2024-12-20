"""empty message

Revision ID: 0029_rom_file_and_hashes
Revises: 0028_user_email
Create Date: 2024-12-19 23:16:11.053536

"""

import sqlalchemy as sa
from alembic import op
from config import IS_PYTEST_RUN, SCAN_TIMEOUT
from endpoints.sockets.scan import scan_platforms
from handler.redis_handler import high_prio_queue
from handler.scan_handler import ScanType
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0029_rom_file_and_hashes"
down_revision = "0028_user_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rom_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("last_modified", sa.Float(), nullable=True),
        sa.Column("crc_hash", sa.String(length=100), nullable=True),
        sa.Column("md5_hash", sa.String(length=100), nullable=True),
        sa.Column("sha1_hash", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO rom_files (
            rom_id,
            file_name,
            file_path,
            file_size_bytes,
            last_modified,
            crc_hash,
            md5_hash,
            sha1_hash
        )
        SELECT
            r.id AS rom_id,
            JSON_UNQUOTE(JSON_EXTRACT(file_data, '$.filename')) AS file_name,
            r.file_path AS file_path,
            JSON_UNQUOTE(JSON_EXTRACT(file_data, '$.size')) AS file_size_bytes,
            JSON_UNQUOTE(JSON_EXTRACT(file_data, '$.last_modified')) AS last_modified,
            CASE WHEN r.multi = 0 THEN r.crc_hash ELSE NULL END AS crc_hash,
            CASE WHEN r.multi = 0 THEN r.md5_hash ELSE NULL END AS md5_hash,
            CASE WHEN r.multi = 0 THEN r.sha1_hash ELSE NULL END AS sha1_hash
        FROM roms r,
        JSON_TABLE(r.files, '$[*]' 
            COLUMNS (
                file_data JSON PATH '$'
            )
        ) AS extracted_files;
        """
    )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "file_name", new_column_name="fs_name", existing_type=sa.String(length=450)
        )
        batch_op.alter_column(
            "file_name_no_tags",
            new_column_name="fs_name_no_tags",
            existing_type=sa.String(length=450),
        )
        batch_op.alter_column(
            "file_name_no_ext",
            new_column_name="fs_name_no_ext",
            existing_type=sa.String(length=450),
        )
        batch_op.alter_column(
            "file_extension",
            new_column_name="fs_extension",
            existing_type=sa.String(length=100),
        )
        batch_op.alter_column(
            "file_path", new_column_name="fs_path", existing_type=sa.String(length=1000)
        )
        batch_op.drop_column("files")
        batch_op.drop_column("multi")
        batch_op.drop_column("file_size_bytes")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=mysql.ENUM("VIEWER", "EDITOR", "ADMIN"),
            nullable=False,
        )
        batch_op.alter_column(
            "avatar_path", existing_type=mysql.VARCHAR(length=255), nullable=False
        )

    # Run a no-scan in the background on migrate
    if not IS_PYTEST_RUN:
        high_prio_queue.enqueue(
            scan_platforms, [], ScanType.QUICK, [], [], job_timeout=SCAN_TIMEOUT
        )

        high_prio_queue.enqueue(
            scan_platforms, [], ScanType.HASHES, [], [], job_timeout=SCAN_TIMEOUT
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "avatar_path", existing_type=mysql.VARCHAR(length=255), nullable=True
        )
        batch_op.alter_column(
            "role", existing_type=mysql.ENUM("VIEWER", "EDITOR", "ADMIN"), nullable=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "multi",
                mysql.TINYINT(display_width=1),
                autoincrement=False,
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "files",
                mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "file_size_bytes",
                mysql.BIGINT(display_width=20),
                autoincrement=False,
                nullable=False,
            )
        )
        batch_op.alter_column(
            "fs_path", new_column_name="file_path", existing_type=sa.String(length=1000)
        )
        batch_op.alter_column(
            "fs_extension",
            new_column_name="file_extension",
            existing_type=sa.String(length=100),
        )
        batch_op.alter_column(
            "fs_name_no_ext",
            new_column_name="file_name_no_ext",
            existing_type=sa.String(length=450),
        )
        batch_op.alter_column(
            "fs_name_no_tags",
            new_column_name="file_name_no_tags",
            existing_type=sa.String(length=450),
        )
        batch_op.alter_column(
            "fs_name", new_column_name="file_name", existing_type=sa.String(length=450)
        )

    op.execute(
        """
        UPDATE roms
        JOIN (
            SELECT 
                rom_id,
                JSON_ARRAYAGG(
                    JSON_OBJECT(
                        'filename', file_name,
                        'size', file_size_bytes,
                        'last_modified', last_modified
                    )
                ) AS files,
                COUNT(*) > 1 AS multi,
                COALESCE(SUM(file_size_bytes), 0) AS total_size
            FROM rom_files
            GROUP BY rom_id
        ) AS aggregated_data
        ON roms.id = aggregated_data.rom_id
        SET 
            roms.files = aggregated_data.files,
            roms.multi = aggregated_data.multi,
            roms.file_size_bytes = aggregated_data.total_size;
        """
    )

    op.drop_table("rom_files")
