from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from handler.database.base_handler import sync_engine
from utils import fulltext
from utils.database import is_postgresql
from utils.fulltext import (
    DEFAULT_FULLTEXT_SETTINGS,
    FulltextSettings,
    fulltext_settings,
    read_fulltext_settings,
    split_fulltext_words,
)

IS_FULLTEXT_ENGINE = not is_postgresql(sync_engine)


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    fulltext._server_fulltext_settings.cache_clear()
    yield
    fulltext._server_fulltext_settings.cache_clear()


def _conn_reporting(
    min_token_size: int = 3,
    *,
    stopwords_enabled: bool = True,
    user_table: str | None = None,
    server_table: str | None = None,
) -> MagicMock:
    conn = MagicMock()
    conn.execute.return_value.one.return_value = (
        min_token_size,
        84,
        int(stopwords_enabled),
        user_table,
        server_table,
    )
    conn.scalars.return_value = ["Foo", "bar", None]
    return conn


def _engine_connecting(conn: MagicMock) -> MagicMock:
    engine = MagicMock()
    engine.engine.name = "mariadb"
    engine.connect.return_value.__enter__.return_value = conn
    return engine


@pytest.mark.skipif(not IS_FULLTEXT_ENGINE, reason="InnoDB full-text only")
def test_reads_the_servers_settings():
    with sync_engine.connect() as conn:
        min_token_size: int = conn.execute(
            text("SELECT @@innodb_ft_min_token_size")
        ).scalar_one()
        settings = read_fulltext_settings(conn)

    assert settings.min_token_size == min_token_size
    assert "the" in settings.stopwords


@pytest.mark.skipif(IS_FULLTEXT_ENGINE, reason="PostgreSQL has no FULLTEXT index")
def test_postgresql_uses_the_defaults():
    assert fulltext_settings(sync_engine) == DEFAULT_FULLTEXT_SETTINGS


def test_skips_fulltext_and_retries_when_the_server_is_unreachable():
    engine = _engine_connecting(MagicMock())
    engine.connect.side_effect = OperationalError("SELECT", {}, Exception("2013"))

    assert fulltext_settings(engine) is None
    assert fulltext_settings(engine) is None

    assert engine.connect.call_count == 2


def test_keeps_the_token_sizes_when_the_stopwords_are_unreadable():
    conn = _conn_reporting(4)
    conn.scalars.side_effect = OperationalError("SELECT", {}, Exception("1227"))

    assert read_fulltext_settings(conn) == DEFAULT_FULLTEXT_SETTINGS._replace(
        min_token_size=4
    )


def test_reads_a_custom_stopword_table():
    conn = _conn_reporting(2, server_table="romm/stopwords")

    settings = read_fulltext_settings(conn)

    query = conn.scalars.call_args.args[0]
    assert "FROM romm.stopwords" in str(query)
    assert settings == FulltextSettings(2, 84, frozenset({"foo", "bar"}))


def test_prefers_the_user_stopword_table():
    conn = _conn_reporting(user_table="romm/mine", server_table="romm/stopwords")

    read_fulltext_settings(conn)

    assert "FROM romm.mine" in str(conn.scalars.call_args.args[0])


def test_unreadable_custom_stopwords_skip_fulltext_and_retry():
    conn = _conn_reporting(server_table="romm/stopwords")
    conn.scalars.side_effect = OperationalError("SELECT", {}, Exception("1142"))

    engine = _engine_connecting(conn)

    assert fulltext_settings(engine) is None
    assert fulltext_settings(engine) is None
    assert conn.scalars.call_count == 2


def test_disabled_stopwords_leave_none():
    conn = _conn_reporting(stopwords_enabled=False)

    assert read_fulltext_settings(conn) == FulltextSettings(3, 84, frozenset())


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("final fantasy 7", (["final", "fantasy"], ["7"])),
        ("the legend", (["legend"], ["the"])),
        # InnoDB reads "dr." as the 2-letter token "dr".
        ("dr. mario", (["mario"], ["dr."])),
        ("pokemon: red", (["pokemon", "red"], [])),
        ("spider-man x-2", (["spider", "man"], ["x-2"])),
        ("mario's", (["mario's"], [])),
        ("a" * 85, ([], ["a" * 85])),
    ],
)
def test_split_fulltext_words(term: str, expected: tuple[list[str], list[str]]):
    assert split_fulltext_words(term.split(), DEFAULT_FULLTEXT_SETTINGS) == expected


def test_split_fulltext_words_follows_the_token_size():
    settings = DEFAULT_FULLTEXT_SETTINGS._replace(min_token_size=2)

    assert split_fulltext_words(["ff", "of"], settings) == (["ff"], ["of"])
