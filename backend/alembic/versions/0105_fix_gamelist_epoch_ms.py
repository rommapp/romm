"""Make romm_gamelist_epoch_ms tolerate calendar-invalid gamelist dates

``generated_first_release_date`` (migration 0098) gates the gamelist branch on
``'^[0-9]{8}T[0-9]{6}$'``, which proves the value is 8+6 digits but not that
those digits form a real date. EmulationStation, ES-DE and Skyscraper all write
``00000000T000000`` when a game has no known release date, and ``make_timestamp``
raises on it. Since the column is STORED, that error aborts the statement: the
0098 ``ALTER TABLE`` for anyone still on 5.0, and every later ``INSERT`` of such
a ROM for anyone who upgraded before a gamelist scan brought one in.

0098 now defines the function defensively, but that only helps installs that
have yet to run it. This replaces the function in place for the rest. Existing
generated values are untouched and need no backfill: they are valid by
construction, or 0098 would not have completed.

MariaDB is unaffected. Its branch of 0098 range-checks the components in SQL
before converting.

Revision ID: 0105_fix_gamelist_epoch_ms
Revises: 0104_roms_missing_from_fs_index
Create Date: 2026-07-30 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0105_fix_gamelist_epoch_ms"
down_revision = "0104_roms_missing_from_fs_index"
branch_labels = None
depends_on = None

# Kept in sync with _GAMELIST_EPOCH_FN in 0098. CREATE OR REPLACE is accepted
# while a STORED generated column depends on the function: the signature is
# unchanged, so no table rewrite happens and only subsequent writes see the new
# body.
_GAMELIST_EPOCH_FN = """
CREATE OR REPLACE FUNCTION romm_gamelist_epoch_ms(s text) RETURNS bigint
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
BEGIN
    RETURN (extract(epoch FROM make_timestamp(
        substr(s, 1, 4)::int, substr(s, 5, 2)::int, substr(s, 7, 2)::int,
        substr(s, 10, 2)::int, substr(s, 12, 2)::int, substr(s, 14, 2)::int
    ) AT TIME ZONE 'UTC') * 1000)::bigint;
EXCEPTION WHEN others THEN
    RETURN NULL;
END
$$
"""


def upgrade() -> None:
    connection = op.get_bind()

    if is_postgresql(connection):
        connection.execute(sa.text(_GAMELIST_EPOCH_FN))


def downgrade() -> None:
    # Restoring the raising definition would only re-break writes, and 0098 (now
    # carrying the same body) drops the function on its own downgrade.
    pass
