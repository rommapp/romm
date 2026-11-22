"""Delete a device's client tokens with the device instead of unbinding them."""

from alembic import op

revision = "0159_client_tokens_fk_cascade"
down_revision = "0158_platform_first_release_year"
branch_labels = None
depends_on = None


def _recreate_device_fk(ondelete: str) -> None:
    with op.batch_alter_table("client_tokens", schema=None) as batch_op:
        batch_op.drop_constraint("fk_client_tokens_device_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_client_tokens_device_id",
            "devices",
            ["device_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    _recreate_device_fk("CASCADE")


def downgrade() -> None:
    _recreate_device_fk("SET NULL")
