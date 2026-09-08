from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import event

from handler.database import db_rom_handler
from handler.database.base_handler import sync_engine
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User

LAST_MODIFIED = 1700000000.0

FILE_STAT_FIELDS = (
    "has_simple_single_file",
    "has_nested_single_file",
    "has_multiple_files",
    "has_soundtrack",
)


def _add_rom(admin_user: User, platform: Platform, name: str, fs_name: str) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=f"{name}_slug",
            fs_name=fs_name,
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension=fs_name.rpartition(".")[2] if "." in fs_name else "",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    return rom


def _add_file(
    rom: Rom,
    file_name: str,
    *,
    file_path: str,
    category: RomFileCategory = RomFileCategory.GAME,
) -> None:
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=file_name,
            file_path=file_path,
            file_size_bytes=10,
            last_modified=LAST_MODIFIED,
            category=category,
        )
    )


@pytest.fixture
def fileless_rom(admin_user: User, platform: Platform) -> Rom:
    """A ROM with no file rows at all, as a scan leaves one missing from disk."""
    return _add_rom(admin_user, platform, "fileless_rom", "fileless_rom.zip")


@pytest.fixture
def flat_rom(admin_user: User, platform: Platform) -> Rom:
    """A single file sitting directly in the platform's roms directory."""
    rom = _add_rom(admin_user, platform, "flat_rom", "flat_rom.zip")
    _add_file(rom, "flat_rom.zip", file_path=rom.fs_path)
    return rom


@pytest.fixture
def folder_rom(admin_user: User, platform: Platform) -> Rom:
    """A folder ROM with two files side by side at its top level."""
    rom = _add_rom(admin_user, platform, "folder_rom", "folder_rom")
    for file_name in ("game.bin", "readme.txt"):
        _add_file(rom, file_name, file_path=f"{rom.fs_path}/folder_rom")
    return rom


@pytest.fixture
def nested_rom(admin_user: User, platform: Platform) -> Rom:
    """A folder ROM whose only content file sits in a subdirectory."""
    rom = _add_rom(admin_user, platform, "nested_rom", "nested_rom")
    _add_file(rom, "disc.bin", file_path=f"{rom.fs_path}/nested_rom/data")
    return rom


@pytest.fixture
def soundtrack_rom(admin_user: User, platform: Platform) -> Rom:
    """A folder ROM carrying a game file and a soundtrack track."""
    rom = _add_rom(admin_user, platform, "ost_rom", "ost_rom")
    file_path = f"{rom.fs_path}/ost_rom"
    _add_file(rom, "game.bin", file_path=file_path)
    _add_file(
        rom, "01.mp3", file_path=f"{file_path}/ost", category=RomFileCategory.SOUNDTRACK
    )
    return rom


def _fetch_one(
    client: TestClient, access_token: str, platform: Platform, *, with_files: bool
) -> dict[str, Any]:
    response = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"platform_ids": platform.id, "with_files": with_files},
    )
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    return items[0]


@pytest.mark.parametrize(
    "rom_fixture",
    ["flat_rom", "folder_rom", "nested_rom", "soundtrack_rom", "fileless_rom"],
)
def test_file_stats_match_between_derived_and_sql_paths(
    client: TestClient,
    access_token: str,
    platform: Platform,
    rom_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Pin the two implementations to each other, not to a hardcoded expectation.

    `with_files=true` derives the flags in Python; `false` reads the subqueries.
    """
    request.getfixturevalue(rom_fixture)

    derived = _fetch_one(client, access_token, platform, with_files=True)
    from_sql = _fetch_one(client, access_token, platform, with_files=False)

    assert {field: derived[field] for field in FILE_STAT_FIELDS} == {
        field: from_sql[field] for field in FILE_STAT_FIELDS
    }


@pytest.fixture
def executed_statements() -> Iterator[list[str]]:
    statements: list[str] = []

    def before_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", before_execute)
    try:
        yield statements
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_execute)


def test_with_files_query_count_does_not_scale_with_file_count(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    executed_statements: list[str],
) -> None:
    """Track metadata is eager-loaded, so files cost a fixed number of queries."""
    rom = _add_rom(admin_user, platform, "many_files_rom", "many_files_rom")
    for index in range(25):
        _add_file(
            rom,
            f"{index:02d}.mp3",
            file_path=f"{rom.fs_path}/many_files_rom/ost",
            category=RomFileCategory.SOUNDTRACK,
        )

    executed_statements.clear()
    item = _fetch_one(client, access_token, platform, with_files=True)
    assert len(item["files"]) == 25

    track_meta_queries = [s for s in executed_statements if "track_meta" in s]
    assert len(track_meta_queries) <= 1
