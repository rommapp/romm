"""The notes routes read a ROM's id and platform id, not the full `get_rom` load."""

from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.rom import Rom
from models.user import User

# The tables `get_rom` eager-loads, minus `rom_notes` and `platforms`, both of
# which the notes queries themselves read.
EAGER_TABLES = (
    "rom_files",
    "roms_metadata",
    "saves",
    "states",
    "screenshots",
    "rom_user",
    "collections_roms",
    "sibling_roms",
    "track_meta",
    "rom_file_doc_meta",
)

# Truncated at the bind placeholder: MariaDB renders `?` and psycopg
# `%(id_1)s::INTEGER`, and CI runs both.
ROM_LOOKUP = "SELECT roms.id, roms.platform_id FROM roms WHERE roms.id ="


def _auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _flat(statements: list[str]) -> list[str]:
    return [" ".join(statement.split()) for statement in statements]


def _reads(statements: list[str], table: str) -> list[str]:
    return [s for s in _flat(statements) if f"FROM {table} " in s]


def _assert_narrow_rom_lookup(statements: list[str]) -> None:
    flat = _flat(statements)

    narrow = [s for s in flat if s.startswith(ROM_LOOKUP)]
    assert len(narrow) == 1, flat

    for table in EAGER_TABLES:
        assert _reads(statements, table) == [], table


def test_note_identifiers_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    db_rom_handler.create_rom_note(rom_id=rom.id, user_id=admin_user.id, title="one")

    executed_statements.clear()
    response = client.get(
        f"/api/roms/{rom.id}/notes/identifiers", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    _assert_narrow_rom_lookup(executed_statements)
    # The route's own note query is the only read; a full `Rom` adds a second.
    assert len(_reads(executed_statements, "rom_notes")) == 1


def test_create_note_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    executed_statements.clear()
    response = client.post(
        f"/api/roms/{rom.id}/notes",
        headers=_auth(access_token),
        json={"title": "from the test"},
    )

    assert response.status_code == status.HTTP_200_OK
    _assert_narrow_rom_lookup(executed_statements)
    assert _reads(executed_statements, "rom_notes") == []


def test_update_note_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    note = db_rom_handler.create_rom_note(
        rom_id=rom.id, user_id=admin_user.id, title="before"
    )

    executed_statements.clear()
    response = client.put(
        f"/api/roms/{rom.id}/notes/{note['id']}",
        headers=_auth(access_token),
        json={"content": "after"},
    )

    assert response.status_code == status.HTTP_200_OK
    _assert_narrow_rom_lookup(executed_statements)
