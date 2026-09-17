"""The rom-notes routes resolve a ROM from its two identifying columns.

The 404 and visibility checks need a ROM's id and platform id and nothing else,
so the routes must not pay for the `get_rom` related load (platform, files,
metadata, saves, states, screenshots, rom_users, siblings, collections, notes).
"""

from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.rom import Rom
from models.user import User

# What `get_rom` eager-loads. None of it backs the id / platform id pair a notes
# route checks before it answers.
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

ROM_LOOKUP = "SELECT roms.id, roms.platform_id FROM roms WHERE roms.id = ?"


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _flat(statements: list[str]) -> list[str]:
    return [" ".join(statement.split()) for statement in statements]


def _reads(statements: list[str], table: str) -> list[str]:
    return [s for s in _flat(statements) if f"FROM {table} " in s]


def _assert_narrow_rom_lookup(statements: list[str]) -> None:
    flat = _flat(statements)

    assert [s for s in flat if s == ROM_LOOKUP] == [ROM_LOOKUP], flat

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
        f"/api/roms/{rom.id}/notes/identifiers", headers=_headers(access_token)
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
        headers=_headers(access_token),
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
        headers=_headers(access_token),
        json={"content": "after"},
    )

    assert response.status_code == status.HTTP_200_OK
    _assert_narrow_rom_lookup(executed_statements)
