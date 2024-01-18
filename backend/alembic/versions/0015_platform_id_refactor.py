"""empty message

Revision ID: 0015_platform_id_refactor
Revises: 0014_asset_files
Create Date: 2024-01-12 02:08:14.962703

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "0015_platform_id_refactor"
down_revision = "0014_asset_files"
branch_labels = None
depends_on = None

SIZE_UNIT_TO_BYTES = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
    "PB": 1024**5,
}


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    # Drop platform_slug foreign key on all tables
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_constraint("states_ibfk_1", type_="foreignkey")
        batch_op.drop_column("platform_slug")

    with op.batch_alter_table("screenshots", schema=None) as batch_op:
        batch_op.drop_constraint("screenshots_ibfk_1", type_="foreignkey")
        batch_op.drop_column("platform_slug")

    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.drop_constraint("saves_ibfk_1", type_="foreignkey")
        batch_op.drop_column("platform_slug")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_constraint("fk_platform_roms", type_="foreignkey")

    # Change platforms primary key
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_constraint(constraint_name="PRIMARY", type_="primary")
        batch_op.drop_column("n_roms")

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.execute(
            "ALTER TABLE platforms ADD COLUMN id INTEGER(11) NOT NULL AUTO_INCREMENT PRIMARY KEY"
        )

    # Create platform id foreign key
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("p_sgdb_id")
        batch_op.drop_column("p_igdb_id")
        batch_op.drop_column("p_name")
        batch_op.add_column(sa.Column("file_size_bytes", sa.Integer(), nullable=False))
        batch_op.add_column(
            sa.Column(
                "platform_id",
                mysql.INTEGER(display_width=11),
                autoincrement=False,
                nullable=False,
            )
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.execute(
            "update roms inner join platforms on roms.platform_slug = platforms.slug set roms.platform_id = platforms.id"
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "roms_platforms_FK", "platforms", ["platform_id"], ["id"]
        )
        batch_op.drop_column("platform_slug")

    connection = op.get_bind()
    result = connection.execute(text("SELECT id, file_size, file_size_units FROM roms"))

    # Process the data and prepare for bulk update
    updates = []
    for row in result:
        file_size_bytes = int(row[1] * SIZE_UNIT_TO_BYTES.get(row[2], 1))
        updates.append({"id": row[0], "file_size_bytes": file_size_bytes})

    if updates:
        # Perform bulk update
        connection.execute(
            text("UPDATE roms SET file_size_bytes = :file_size_bytes WHERE id = :id"),
            updates,
        )

    # Clean roms table
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("file_size")
        batch_op.drop_column("file_size_units")
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("id")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("platform_slug", sa.String(length=50), nullable=False)
        )
        batch_op.add_column(sa.Column("p_name", sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column("p_igdb_id", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("p_sgdb_id", sa.String(length=10), nullable=True))
        batch_op.drop_constraint("roms_platforms_FK", type_="foreignkey")
        batch_op.create_foreign_key(None, "platforms", ["platform_slug"], ["slug"])
        batch_op.drop_column("platform_id")
        batch_op.drop_column("file_size_bytes")
        batch_op.add_column(
            sa.Column("file_size_units", sa.String(length=10), nullable=False)
        )
        batch_op.add_column(sa.Column("file_size", sa.Float(), nullable=False))

    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("platform_slug", sa.String(length=50), nullable=False)
        )
        batch_op.create_foreign_key(
            None, "platforms", ["platform_slug"], ["slug"], ondelete="CASCADE"
        )

    with op.batch_alter_table("screenshots", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("platform_slug", sa.String(length=50), nullable=True)
        )
        batch_op.create_foreign_key(
            None, "platforms", ["platform_slug"], ["slug"], ondelete="CASCADE"
        )

    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("platform_slug", sa.String(length=50), nullable=False)
        )
        batch_op.create_foreign_key(
            None, "platforms", ["platform_slug"], ["slug"], ondelete="CASCADE"
        )
    # ### end Alembic commands ###