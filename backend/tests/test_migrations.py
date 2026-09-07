"""Guard the models against drifting away from the migrated schema.

An index is easy to add in a migration and forget on the model. Once that
happens the next `alembic revision --autogenerate` proposes dropping it, and
nothing else in the suite notices, because the test database is built from the
migrations rather than from the models.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection

from handler.database.base_handler import sync_engine
from models.base import BaseModel
from utils.database import AUTOGENERATE_EXEMPT_INDEX_NAMES

# `compare_metadata` yields flat tuples for schema-level diffs, and a list of
# tuples for column-level ones. Only these two name an index.
INDEX_DIFF_OPS = frozenset({"add_index", "remove_index"})


def _include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Mirror the index exemptions in `alembic/env.py`.

    env.py is an alembic entrypoint script and reads `context.config` at import
    time, so it can't be imported here; the exempt names are shared instead.
    """
    return not (type_ == "index" and name in AUTOGENERATE_EXEMPT_INDEX_NAMES)


def _index_diffs(connection: Connection) -> list[str]:
    context = MigrationContext.configure(
        connection, opts={"include_object": _include_object}
    )
    return [
        f"{diff[0]}: {diff[1].name} on {diff[1].table.name}"
        for diff in compare_metadata(context, BaseModel.metadata)
        if not isinstance(diff, list) and diff[0] in INDEX_DIFF_OPS
    ]


def test_no_index_drift_between_models_and_migrations():
    """Every migrated index is declared on its model, and vice versa.

    A failure names the index. If the migrations are right, declare it in the
    model's `__table_args__` (or as `index=True`). If it genuinely can't be
    declared because it is dialect-specific, add it to
    `AUTOGENERATE_EXEMPT_INDEX_NAMES`.
    """
    with sync_engine.connect() as connection:
        assert _index_diffs(connection) == []
