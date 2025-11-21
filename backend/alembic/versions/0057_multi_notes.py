"""rom_notes_table

Revision ID: 0057_multi_notes
Revises: 0056_gamelist_xml
Create Date: 2025-09-29 14:20:28.990148

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0057_multi_notes"
down_revision = "0056_gamelist_xml"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the rom_notes table and migrate existing notes."""

    # Create the new rom_notes table
    op.create_table(
        "rom_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=400), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, default=False),
        sa.Column("tags", sa.JSON(), nullable=True),
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
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rom_id", "user_id", "title", name="unique_rom_user_note_title"
        ),
    )

    # Create indexes for performance
    op.create_index("idx_rom_notes_public", "rom_notes", ["is_public"])
    op.create_index("idx_rom_notes_rom_user", "rom_notes", ["rom_id", "user_id"])

    # Get connection for manual index creation
    connection = op.get_bind()
    # For MariaDB compatibility, we limit the content index length
    connection.execute(text("CREATE INDEX idx_rom_notes_title ON rom_notes (title)"))
    connection.execute(
        text("CREATE INDEX idx_rom_notes_content ON rom_notes (content(100))")
    )

    # Add default values to old note columns to prevent insertion errors
    # This allows new rom_user records to be created without specifying note fields
    op.alter_column(
        "rom_user",
        "note_raw_markdown",
        existing_type=sa.Text(),
        server_default="",
        nullable=True,
    )
    op.alter_column(
        "rom_user",
        "note_is_public",
        existing_type=sa.Boolean(),
        server_default=text("false"),
        nullable=True,
    )

    # Migrate existing notes from rom_user to rom_notes table
    # Both note_raw_markdown and note_is_public columns exist from previous migrations
    connection = op.get_bind()
    result = connection.execute(
        text(
            """
            SELECT id, rom_id, user_id, note_raw_markdown, note_is_public, updated_at
            FROM rom_user
        """
        )
    )

    for row in result:
        connection.execute(
            text(
                """
                INSERT INTO rom_notes (title, content, is_public, tags, created_at, updated_at, rom_id, user_id)
                VALUES (:title, :content, :is_public, :tags, :created_at, :updated_at, :rom_id, :user_id)
            """
            ),
            {
                "title": "My Note",
                "content": row.note_raw_markdown or "",  # Handle potential NULL content
                "is_public": row.note_is_public,
                "tags": "[]",
                "created_at": row.updated_at or text("now()"),
                "updated_at": row.updated_at or text("now()"),
                "rom_id": row.rom_id,
                "user_id": row.user_id,
            },
        )
        # Remove the old note columns from rom_user table in a future migration
        # op.drop_column("rom_user", "note_raw_markdown")
        # op.drop_column("rom_user", "note_is_public")


def downgrade() -> None:
    """Drop the rom_notes table and restore note columns to rom_user."""

    # Add back the old columns to rom_user
    op.add_column(
        "rom_user",
        sa.Column("note_raw_markdown", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "rom_user",
        sa.Column(
            "note_is_public", sa.Boolean(), nullable=False, server_default=text("false")
        ),
    )

    # Migrate notes back to rom_user (take first note per user/rom)
    connection = op.get_bind()
    result = connection.execute(
        text(
            """
            SELECT DISTINCT rom_id, user_id, 
                   FIRST_VALUE(content) OVER (PARTITION BY rom_id, user_id ORDER BY updated_at DESC) as content,
                   FIRST_VALUE(is_public) OVER (PARTITION BY rom_id, user_id ORDER BY updated_at DESC) as is_public
            FROM rom_notes
        """
        )
    )

    for row in result:
        connection.execute(
            text(
                """
                UPDATE rom_user 
                SET note_raw_markdown = :content, note_is_public = :is_public 
                WHERE rom_id = :rom_id AND user_id = :user_id
            """
            ),
            {
                "content": row.content,
                "is_public": row.is_public,
                "rom_id": row.rom_id,
                "user_id": row.user_id,
            },
        )

    # Drop indexes and table
    connection = op.get_bind()
    connection.execute(text("DROP INDEX IF EXISTS idx_rom_notes_content ON rom_notes"))
    connection.execute(text("DROP INDEX IF EXISTS idx_rom_notes_title ON rom_notes"))
    op.drop_index("idx_rom_notes_rom_user", table_name="rom_notes")
    op.drop_index("idx_rom_notes_public", table_name="rom_notes")
    op.drop_table("rom_notes")
