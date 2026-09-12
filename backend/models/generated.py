"""Dialect-dispatched expressions behind the STORED generated columns on `roms`.

Each expression renders per dialect, so one model declaration serves MariaDB,
MySQL and PostgreSQL. The revisions that first created these columns keep their
own literal copy: a migration that read its DDL from here would rewrite itself
the day the expression changed.
"""

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement

_MARIA_HLTB_VALUE = (
    "CAST(JSON_UNQUOTE(JSON_EXTRACT(hltb_metadata, '$.main_story')) AS CHAR)"
)
_POSTGRES_HLTB_VALUE = "hltb_metadata ->> 'main_story'"


class HltbMainStory(ColumnElement):
    """HowLongToBeat's main-story time in seconds, or NULL for a malformed blob.

    MariaDB unquotes before the numeric CAST so a STORED INSERT does not trip
    strict-mode truncation, and the digits-only gate keeps a bad blob from
    aborting the write (0098, 0128).
    """

    inherit_cache = True


@compiles(HltbMainStory, "mysql")
@compiles(HltbMainStory, "mariadb")
def _hltb_main_story_maria(element: HltbMainStory, compiler, **kw) -> str:
    return (
        "CASE WHEN JSON_CONTAINS_PATH(hltb_metadata, 'one', '$.main_story') "
        f"AND {_MARIA_HLTB_VALUE} NOT IN ('null', 'None', '0', '0.0') "
        f"AND {_MARIA_HLTB_VALUE} REGEXP '^[0-9]+$' "
        f"THEN CAST({_MARIA_HLTB_VALUE} AS SIGNED) ELSE NULL END"
    )


@compiles(HltbMainStory, "postgresql")
def _hltb_main_story_postgres(element: HltbMainStory, compiler, **kw) -> str:
    return (
        "CASE WHEN hltb_metadata IS NOT NULL AND hltb_metadata ? 'main_story' "
        f"AND ({_POSTGRES_HLTB_VALUE}) NOT IN ('null', 'None', '0', '0.0') "
        f"AND ({_POSTGRES_HLTB_VALUE}) ~ '^[0-9]+$' "
        f"THEN ({_POSTGRES_HLTB_VALUE})::bigint ELSE NULL END"
    )
