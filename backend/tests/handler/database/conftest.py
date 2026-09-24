"""Driver fixtures for query-shape tests: the suite runs one database at a
time, so dialect branches are pinned by patching the handler's constant."""

import pytest

_DRIVER_ATTR = "handler.database.roms_handler.ROMM_DB_DRIVER"


@pytest.fixture
def mariadb_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_DRIVER_ATTR, "mariadb")


@pytest.fixture
def postgres_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_DRIVER_ATTR, "postgresql")
