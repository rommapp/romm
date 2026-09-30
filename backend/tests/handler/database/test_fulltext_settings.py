from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from handler.database import roms_handler
from handler.database.base_handler import sync_engine
from handler.database.roms_handler import (
    DEFAULT_FULLTEXT_SETTINGS,
    FulltextSettings,
    _stopword_table,
    fulltext_settings,
)

IS_FULLTEXT_ENGINE = sync_engine.name in ("mariadb", "mysql")


@pytest.fixture(autouse=True)
def fresh_settings() -> Iterator[None]:
    fulltext_settings.cache_clear()
    yield
    fulltext_settings.cache_clear()


def _engine_returning(
    min_token_size: int, stopwords_enabled: int, server_table: str | None
) -> MagicMock:
    engine = MagicMock()
    engine.name = "mariadb"
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.one.return_value = (
        min_token_size,
        stopwords_enabled,
        server_table,
    )
    conn.scalars.return_value.all.return_value = ["Foo", "bar"]
    return engine


@pytest.mark.skipif(not IS_FULLTEXT_ENGINE, reason="InnoDB full-text only")
def test_reads_the_servers_settings():
    with sync_engine.connect() as conn:
        min_token_size = conn.execute(
            text("SELECT @@innodb_ft_min_token_size")
        ).scalar_one()

    settings = fulltext_settings()

    assert settings.min_token_size == min_token_size
    assert "the" in settings.stopwords


@pytest.mark.skipif(IS_FULLTEXT_ENGINE, reason="PostgreSQL has no FULLTEXT index")
def test_postgresql_uses_the_defaults():
    assert fulltext_settings() == DEFAULT_FULLTEXT_SETTINGS


def test_falls_back_when_the_server_refuses():
    engine = MagicMock()
    engine.name = "mysql"
    engine.connect.side_effect = OperationalError("SELECT", {}, Exception("1227"))

    with patch.object(roms_handler, "sync_engine", engine):
        assert fulltext_settings() == DEFAULT_FULLTEXT_SETTINGS


def test_reads_a_custom_stopword_table():
    engine = _engine_returning(2, 1, "romm/stopwords")

    with patch.object(roms_handler, "sync_engine", engine):
        settings = fulltext_settings()

    conn = engine.connect.return_value.__enter__.return_value
    assert "FROM `romm`.`stopwords`" in str(conn.scalars.call_args.args[0])
    assert settings == FulltextSettings(2, frozenset({"foo", "bar"}))


def test_disabled_stopwords_leave_none():
    with patch.object(roms_handler, "sync_engine", _engine_returning(3, 0, None)):
        assert fulltext_settings() == FulltextSettings(3, frozenset())


def test_stopword_table_quotes_each_part():
    assert _stopword_table("romm/stop`words") == "`romm`.`stop``words`"
