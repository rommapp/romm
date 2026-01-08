"""Add upload support for walkthroughs

Revision ID: 0064_walkthrough_uploads
Revises: 0063_walkthroughs
Create Date: 2026-01-05 15:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0064_walkthrough_uploads"
down_revision: Union[str, None] = "0063_walkthroughs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "walkthroughs", sa.Column("file_path", sa.String(length=1000), nullable=True)
    )

    # Expand enums to support uploads and PDFs
    op.execute(
        "ALTER TABLE walkthroughs MODIFY COLUMN source ENUM('GAMEFAQS','STEAM','UPLOAD') NOT NULL"
    )
    op.execute(
        "ALTER TABLE walkthroughs MODIFY COLUMN format ENUM('html','text','pdf') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE walkthroughs MODIFY COLUMN source ENUM('GAMEFAQS','STEAM') NOT NULL"
    )
    op.execute(
        "ALTER TABLE walkthroughs MODIFY COLUMN format ENUM('html','text') NOT NULL"
    )
    op.drop_column("walkthroughs", "file_path")
