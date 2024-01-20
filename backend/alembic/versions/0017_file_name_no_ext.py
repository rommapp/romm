"""empty message

Revision ID: 0017_file_name_no_ext
Revises: 0016_file_size_bytes_bigint
Create Date: 2024-01-20 13:54:32.458301

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0017_file_name_no_ext'
down_revision = '0016_file_size_bytes_bigint'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('roms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_name_no_ext', sa.String(length=450), nullable=False))
    
    op.execute("UPDATE roms SET file_name_no_ext = regexp_replace(file_name, '\\.[a-z]{2,}$', '')")

    with op.batch_alter_table('saves', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_name_no_ext', sa.String(length=450), nullable=False))
    
    op.execute("UPDATE saves SET file_name_no_ext = regexp_replace(file_name, '\\.[a-z]{2,}$', '')")

    with op.batch_alter_table('screenshots', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_name_no_ext', sa.String(length=450), nullable=False))
    
    op.execute("UPDATE screenshots SET file_name_no_ext = regexp_replace(file_name, '\\.[a-z]{2,}$', '')")

    with op.batch_alter_table('states', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_name_no_ext', sa.String(length=450), nullable=False))
    
    op.execute("UPDATE states SET file_name_no_ext = regexp_replace(file_name, '\\.[a-z]{2,}$', '')")


def downgrade() -> None:
    with op.batch_alter_table('states', schema=None) as batch_op:
        batch_op.drop_column('file_name_no_ext')

    with op.batch_alter_table('screenshots', schema=None) as batch_op:
        batch_op.drop_column('file_name_no_ext')

    with op.batch_alter_table('saves', schema=None) as batch_op:
        batch_op.drop_column('file_name_no_ext')

    with op.batch_alter_table('roms', schema=None) as batch_op:
        batch_op.drop_column('file_name_no_ext')
