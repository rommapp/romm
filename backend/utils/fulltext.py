"""InnoDB's full-text settings, and how its parser splits search words."""

import functools
import re
from collections.abc import Iterable
from typing import NamedTuple

from sqlalchemy import Connection, Engine, String
from sqlalchemy import column as sql_column
from sqlalchemy import select
from sqlalchemy import table as sql_table
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from logger.logger import log
from utils.database import is_postgresql

# The tokens InnoDB's parser reads out of a word: "dr." holds only "dr".
FULLTEXT_TOKEN_REGEX = re.compile(r"\w+(?:'\w+)*")


class FulltextSettings(NamedTuple):
    min_token_size: int
    max_token_size: int
    stopwords: frozenset[str]


# InnoDB's defaults, for what the server won't report. The index skips
# stopwords, so a required `+the*` would match nothing.
DEFAULT_FULLTEXT_SETTINGS = FulltextSettings(
    min_token_size=3,
    max_token_size=84,
    stopwords=frozenset(
        "a about an are as at be by com de en for from how i in is it la of on or"
        " that the this to und was what when where who will with www".split()
    ),
)


def read_fulltext_settings(conn: Connection) -> FulltextSettings:
    """The server's InnoDB full-text settings; raises if they can't be read."""
    min_size, max_size, stopwords_enabled, user_table, server_table = conn.execute(
        text(
            "SELECT @@innodb_ft_min_token_size, @@innodb_ft_max_token_size,"
            " @@innodb_ft_enable_stopword, @@innodb_ft_user_stopword_table,"
            " @@innodb_ft_server_stopword_table"
        )
    ).one()
    stopwords: frozenset[str] = frozenset()
    if stopwords_enabled:
        custom_table = user_table or server_table
        schema, _, name = (
            custom_table or "information_schema/INNODB_FT_DEFAULT_STOPWORD"
        ).rpartition("/")
        query = select(sql_column("value", String)).select_from(
            sql_table(name, schema=schema or None)
        )
        try:
            stopwords = frozenset(word.lower() for word in conn.scalars(query) if word)
        except SQLAlchemyError as exc:
            if custom_table:
                raise
            # MySQL needs PROCESS for INNODB_FT_DEFAULT_STOPWORD, which holds these.
            log.warning(f"Using InnoDB's default full-text stopwords: {exc}")
            stopwords = DEFAULT_FULLTEXT_SETTINGS.stopwords
    return FulltextSettings(int(min_size), int(max_size), stopwords)


@functools.cache
def _server_fulltext_settings(engine: Engine) -> FulltextSettings:
    with engine.connect() as conn:
        return read_fulltext_settings(conn)


def fulltext_settings(engine: Engine) -> FulltextSettings | None:
    """The server's InnoDB full-text settings, or None while they can't be read."""
    if is_postgresql(engine):
        return DEFAULT_FULLTEXT_SETTINGS
    try:
        return _server_fulltext_settings(engine)
    except SQLAlchemyError as exc:
        # Left uncached, so a transient failure is retried on the next search.
        log.warning(f"Can't read the full-text settings: {exc}")
        return None


def split_fulltext_words(
    words: Iterable[str], settings: FulltextSettings
) -> tuple[list[str], list[str]]:
    """Words as (tokens a FULLTEXT index holds, words it can't hold)."""
    indexed: list[str] = []
    unindexed: list[str] = []
    for word in words:
        tokens = FULLTEXT_TOKEN_REGEX.findall(word)
        if tokens and all(
            settings.min_token_size <= len(token) <= settings.max_token_size
            and token.lower() not in settings.stopwords
            for token in tokens
        ):
            indexed.extend(tokens)
        else:
            unindexed.append(word)
    return indexed, unindexed
