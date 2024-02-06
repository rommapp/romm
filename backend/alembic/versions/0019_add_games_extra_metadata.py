"""empty message

Revision ID: 0019_add_games_extra_metadata
Revises: 0018_increase_file_extension
Create Date: 2024-02-02 16:47:26.098480

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0019_add_games_extra_metadata"
down_revision = "0018_increase_file_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("igdb_metadata", mysql.JSON(), nullable=True))
        batch_op.alter_column(
            "file_extension", existing_type=mysql.VARCHAR(length=100), nullable=False
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.execute("UPDATE roms SET igdb_metadata = '\\{\\}'")
        batch_op.execute(
            "UPDATE roms SET path_cover_s = '', path_cover_l = '', url_cover = '' where url_cover = 'https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png'"
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension", existing_type=mysql.VARCHAR(length=100), nullable=True
        )
        batch_op.drop_column("igdb_metadata")
