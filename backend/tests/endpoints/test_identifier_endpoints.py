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


def _flat(statement: str) -> str:
    return " ".join(statement.split())


def _reads_from(statement: str, table: str) -> bool:
    return f"FROM {table} " in statement or statement.endswith(f"FROM {table}")


def _selects_only_the_id(statement: str, table: str) -> bool:
    """Whether one statement's select list is just `table`'s id column."""
    select_list, separator, _ = statement.partition(" FROM ")
    if not separator:
        return False
    # `Query.with_entities` labels the column (`rom_notes.id AS rom_notes_id`).
    columns = [
        column.split(" AS ")[0].strip()
        for column in select_list[len("SELECT ") :].split(",")
    ]
    return columns == [f"{table}.id"]


def _read_of(statements: list[str], table: str) -> str:
    """The one statement that reads from `table`, whitespace-normalized."""
    reads = [flat for raw in statements if _reads_from(flat := _flat(raw), table)]
    assert len(reads) == 1, reads
    return reads[0]


def _assert_id_only(statements: list[str], table: str) -> None:
    """Assert `table` is read by a bare `SELECT <table>.id` with no join."""
    statement = _read_of(statements, table)
    assert _selects_only_the_id(statement, table), statement
    assert "JOIN" not in statement.partition(" FROM ")[2].upper(), statement


def _assert_table_untouched(statements: list[str], table: str) -> None:
    touching = [flat for raw in statements if _reads_from(flat := _flat(raw), table)]
    assert touching == [], touching


def _id_only_reads(statements: list[str], table: str) -> list[str]:
    """The statements reading `table` whose select list is just its id column."""
    return [
        flat
        for raw in statements
        if _reads_from(flat := _flat(raw), table) and _selects_only_the_id(flat, table)
    ]


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
    """`list_firmware` noloads the platform, so only the projection is under test."""
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
    client: TestClient,
    access_token: str,
    rom: Rom,
    admin_user: User,
    executed_statements: list[str],
) -> None:
    note = db_rom_handler.create_rom_note(
        rom_id=rom.id, user_id=admin_user.id, title="test_note", content="body"
    )

    executed_statements.clear()
    response = client.get(
        f"/api/roms/{rom.id}/notes/identifiers", headers=_headers(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [note["id"]]
    # The route's own `get_rom` check is a separate eager path, so this counts
    # only the projection the ids come from.
    reads = _id_only_reads(executed_statements, "rom_notes")
    assert len(reads) == 1, reads
    assert "JOIN" not in reads[0].upper(), reads[0]
