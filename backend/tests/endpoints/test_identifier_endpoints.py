"""The `/identifiers` endpoints answer from the id column, not from loaded rows.

`load_only(Model.id)` still builds an entity per row, and an eager load on the
model fires anyway, so only a column projection is enough.
"""

from fastapi import status
from fastapi.testclient import TestClient

from handler.database import (
    db_collection_handler,
    db_rom_handler,
)
from models.assets import Save, State
from models.collection import SmartCollection
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _read_of(statements: list[str], table: str) -> str:
    """The one statement that reads from `table`, whitespace-normalized."""
    reads = []
    for raw in statements:
        flat = " ".join(raw.split())
        if f"FROM {table} " in flat or flat.endswith(f"FROM {table}"):
            reads.append(flat)
    assert len(reads) == 1, reads
    return reads[0]


def _assert_id_only(statements: list[str], table: str) -> None:
    """Assert `table` is read by a bare `SELECT <table>.id` with no join."""
    statement = _read_of(statements, table)
    select_list, _, rest = statement.partition(" FROM ")
    # `Query.with_entities` labels the column (`rom_notes.id AS rom_notes_id`).
    columns = [
        column.split(" AS ")[0].strip()
        for column in select_list[len("SELECT ") :].split(",")
    ]
    assert columns == [f"{table}.id"], statement
    assert "JOIN" not in rest.upper(), statement


def _assert_table_untouched(statements: list[str], table: str) -> None:
    touching = [s for s in statements if f"FROM {table} " in " ".join(s.split())]
    assert touching == [], touching


def test_save_identifiers_does_not_load_the_roms_it_points_at(
    client: TestClient,
    access_token: str,
    save: Save,
    executed_statements: list[str],
) -> None:
    executed_statements.clear()
    response = client.get("/api/saves/identifiers", headers=_headers(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [save.id]
    _assert_id_only(executed_statements, "saves")
    _assert_table_untouched(executed_statements, "roms")


def test_state_identifiers_does_not_load_the_roms_it_points_at(
    client: TestClient,
    access_token: str,
    state: State,
    executed_statements: list[str],
) -> None:
    executed_statements.clear()
    response = client.get("/api/states/identifiers", headers=_headers(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [state.id]
    _assert_id_only(executed_statements, "states")
    _assert_table_untouched(executed_statements, "roms")


def test_firmware_identifiers_selects_only_the_id_column(
    client: TestClient,
    access_token: str,
    firmware: Firmware,
    missing_firmware: Firmware,
    executed_statements: list[str],
) -> None:
    executed_statements.clear()
    response = client.get("/api/firmware/identifiers", headers=_headers(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert sorted(response.json()) == sorted([firmware.id, missing_firmware.id])
    _assert_id_only(executed_statements, "firmware")


def test_platform_identifiers_does_not_load_the_firmware_it_ignores(
    client: TestClient,
    access_token: str,
    platform: Platform,
    other_platform: Platform,
    firmware: Firmware,
    executed_statements: list[str],
) -> None:
    """`with_firmware` eager-loads every firmware row for the listed platforms."""
    executed_statements.clear()
    response = client.get("/api/platforms/identifiers", headers=_headers(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert sorted(response.json()) == sorted([platform.id, other_platform.id])
    _assert_id_only(executed_statements, "platforms")
    _assert_table_untouched(executed_statements, "firmware")


def test_smart_collection_identifiers_does_not_load_the_owner(
    client: TestClient,
    access_token: str,
    admin_user: User,
    executed_statements: list[str],
) -> None:
    collection = db_collection_handler.add_smart_collection(
        SmartCollection(
            name="test_smart_collection",
            user_id=admin_user.id,
            filter_criteria={"order_by": "name", "order_dir": "asc"},
        )
    )

    executed_statements.clear()
    response = client.get(
        "/api/collections/smart/identifiers", headers=_headers(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [collection.id]
    _assert_id_only(executed_statements, "smart_collections")


def test_rom_note_identifiers_does_not_load_the_roms_it_points_at(
    admin_user: User,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    """Handler-level: the endpoint's own `get_rom` call is a separate eager path."""
    note = db_rom_handler.create_rom_note(
        rom_id=rom.id, user_id=admin_user.id, title="test_note", content="body"
    )

    executed_statements.clear()
    ids = db_rom_handler.get_rom_note_ids(rom_id=rom.id, user_id=admin_user.id)

    assert ids == [note["id"]]
    _assert_id_only(executed_statements, "rom_notes")
