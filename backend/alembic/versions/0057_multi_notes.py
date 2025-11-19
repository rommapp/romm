"""multi_notes_conversion

Revision ID: 0057_multi_notes
Revises: 0056_gamelist_xml
Create Date: 2025-09-29 14:20:28.990148

"""

import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0057_multi_notes"
down_revision = "0056_gamelist_xml"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert single note fields to multi-note JSON structure."""

    # First, add the new JSON column
    op.add_column("rom_user", sa.Column("notes", sa.JSON(), nullable=True))

    # Get connection to perform data migration
    connection = op.get_bind()

    # Migrate existing notes to the new JSON structure
    result = connection.execute(
        text(
            """
        SELECT id, note_raw_markdown, note_is_public, updated_at 
        FROM rom_user 
        WHERE note_raw_markdown IS NOT NULL AND note_raw_markdown != ''
    """
        )
    )

    for row in result:
        # Create the multi-note structure with the existing note as "Default Note"
        notes_json = {}
        if row.note_raw_markdown and row.note_raw_markdown.strip():
            notes_json["Default Note"] = {
                "content": row.note_raw_markdown,
                "is_public": bool(row.note_is_public),
                "created_at": (
                    row.updated_at.isoformat()
                    if row.updated_at
                    else datetime.now(timezone.utc).isoformat()
                ),
                "updated_at": (
                    row.updated_at.isoformat()
                    if row.updated_at
                    else datetime.now(timezone.utc).isoformat()
                ),
            }

        # Update the row with the JSON data
        connection.execute(
            text(
                """
            UPDATE rom_user 
            SET notes = :notes_json 
            WHERE id = :id
        """
            ),
            {"notes_json": json.dumps(notes_json), "id": row.id},
        )

    # Set empty JSON object for rows with no notes
    connection.execute(
        text(
            """
        UPDATE rom_user 
        SET notes = '{}' 
        WHERE notes IS NULL
    """
        )
    )

    # Make the notes column non-nullable with proper MySQL syntax
    op.alter_column("rom_user", "notes", existing_type=sa.JSON(), nullable=False)

    # Remove the old single-note columns
    op.drop_column("rom_user", "note_raw_markdown")
    op.drop_column("rom_user", "note_is_public")


def downgrade() -> None:
    """Convert multi-note JSON structure back to single note fields."""

    # Add back the old columns
    op.add_column(
        "rom_user",
        sa.Column("note_raw_markdown", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "rom_user",
        sa.Column("note_is_public", sa.Boolean(), nullable=False, server_default="0"),
    )

    # Get connection to perform data migration
    connection = op.get_bind()

    # Migrate JSON notes back to single note format
    result = connection.execute(
        text(
            """
        SELECT id, notes, updated_at 
        FROM rom_user 
        WHERE notes IS NOT NULL
    """
        )
    )

    for row in result:
        try:
            notes_data = json.loads(row.notes) if row.notes else {}

            # Take the first note or "Default Note" if it exists
            if notes_data:
                if "Default Note" in notes_data:
                    note_data = notes_data["Default Note"]
                else:
                    # Take the first note if no "Default Note" exists
                    note_data = next(iter(notes_data.values()))

                content = note_data.get("content", "")
                is_public = note_data.get("is_public", False)
            else:
                content = ""
                is_public = False

            # Update the row with single note data
            connection.execute(
                text(
                    """
                UPDATE rom_user 
                SET note_raw_markdown = :content, note_is_public = :is_public 
                WHERE id = :id
            """
                ),
                {"content": content, "is_public": is_public, "id": row.id},
            )

        except (json.JSONDecodeError, KeyError, TypeError):
            # If JSON parsing fails, set empty note
            connection.execute(
                text(
                    """
                UPDATE rom_user 
                SET note_raw_markdown = '', note_is_public = 0 
                WHERE id = :id
            """
                ),
                {"id": row.id},
            )

    # Drop the JSON column
    op.drop_column("rom_user", "notes")
