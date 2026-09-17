"""The rom-file and rom-props routes resolve a rom without the related load."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User

# Truncated at the bind placeholder: MariaDB renders `?` and psycopg
# `%(id_1)s::INTEGER`, and CI runs both.
VISIBILITY_LOOKUP = "SELECT roms.id, roms.platform_id FROM roms WHERE roms.id ="
LABEL_LOOKUP = (
    "SELECT roms.id, roms.platform_id, roms.name, roms.fs_name "
    "FROM roms WHERE roms.id ="
)
# The bulk delete joins the platform to log its label when a file is already
# missing from disk, so its projection is wider than the label pair.
DELETE_TARGET_LOOKUP = (
    "SELECT roms.id, roms.platform_id, roms.name, roms.fs_name, roms.fs_path, "
    "platforms.slug AS platform_slug"
)

FILE_NAMES = {
    RomFileCategory.GAME: "game.zip",
    RomFileCategory.MANUAL: "manual.pdf",
    RomFileCategory.WALKTHROUGH: "guide.md",
    RomFileCategory.SCREENSHOT: "shot.jpg",
    RomFileCategory.SOUNDTRACK: "track.mp3",
}

DELETE_ROUTES = {
    RomFileCategory.MANUAL: "/api/roms/{rom_id}/manuals/files/{file_id}",
    RomFileCategory.WALKTHROUGH: "/api/roms/{rom_id}/walkthroughs/files/{file_id}",
    RomFileCategory.SCREENSHOT: "/api/roms/{rom_id}/screenshots/{file_id}",
    RomFileCategory.SOUNDTRACK: "/api/roms/{rom_id}/soundtracks/{file_id}",
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _flat(statements: list[str]) -> list[str]:
    return [" ".join(statement.split()) for statement in statements]


def _rom_lookup(statements: list[str], prefix: str, count: int = 1) -> None:
    """Assert exactly `count` statement prefixes match."""
    flat = _flat(statements)
    # `get_rom` selects an aliased `roms_1` shape, so a regression matches zero.
    matches = [s for s in flat if s.startswith(prefix)]

    assert len(matches) == count, flat


def _add_file(rom: Rom, category: RomFileCategory) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=FILE_NAMES[category],
            file_path=rom.fs_path,
            file_size_bytes=1000,
            category=category,
        )
    )


def _hide(rom_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=PermEntity.ROMS, entity_id=rom_id, user_id=user_id))


def test_props_updates_resolve_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    executed_statements.clear()
    response = client.put(
        f"/api/roms/{rom.id}/props", headers=_auth(access_token), json={"hidden": True}
    )

    assert response.status_code == status.HTTP_200_OK
    _rom_lookup(executed_statements, VISIBILITY_LOOKUP)


def test_soundtrack_metadata_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    _add_file(rom, RomFileCategory.SOUNDTRACK)

    executed_statements.clear()
    response = client.get(
        f"/api/roms/{rom.id}/soundtracks/metadata", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    _rom_lookup(executed_statements, VISIBILITY_LOOKUP)


def test_file_progress_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    manual = _add_file(rom, RomFileCategory.MANUAL)

    executed_statements.clear()
    response = client.get(
        f"/api/roms/{rom.id}/files/{manual.id}/progress", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    _rom_lookup(executed_statements, VISIBILITY_LOOKUP)


@pytest.mark.parametrize("category", list(DELETE_ROUTES))
def test_delete_rom_file_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    rom: Rom,
    category: RomFileCategory,
    executed_statements: list[str],
) -> None:
    rom_file = _add_file(rom, category)

    executed_statements.clear()
    response = client.delete(
        DELETE_ROUTES[category].format(rom_id=rom.id, file_id=rom_file.id),
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    _rom_lookup(executed_statements, LABEL_LOOKUP)


def test_delete_game_file_resolves_the_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    rom_file = _add_file(rom, RomFileCategory.GAME)

    executed_statements.clear()
    response = client.delete(
        f"/api/roms/{rom.id}/files/{rom_file.id}", headers=_auth(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    _rom_lookup(executed_statements, LABEL_LOOKUP)


def test_bulk_delete_resolves_each_rom_without_the_related_load(
    client: TestClient,
    access_token: str,
    platform: Platform,
    admin_user: User,
    executed_statements: list[str],
) -> None:
    targets = []
    for n in range(3):
        target = db_rom_handler.add_rom(
            Rom(
                platform_id=platform.id,
                name=f"bulk {n}",
                slug=f"bulk_{n}",
                fs_name=f"bulk_{n}.zip",
                fs_name_no_tags=f"bulk_{n}",
                fs_name_no_ext=f"bulk_{n}",
                fs_extension="zip",
                fs_path=f"{platform.slug}/roms",
            )
        )
        db_rom_handler.add_rom_user(rom_id=target.id, user_id=admin_user.id)
        targets.append(target)

    executed_statements.clear()
    response = client.post(
        "/api/roms/delete",
        headers=_auth(access_token),
        json={"roms": [r.id for r in targets], "delete_from_fs": []},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["successful_items"] == len(targets)

    _rom_lookup(executed_statements, DELETE_TARGET_LOOKUP, count=len(targets))


def test_hidden_rom_file_read_resolves_the_rom_without_the_related_load(
    client: TestClient,
    viewer_access_token: str,
    viewer_user: User,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    rom_file = _add_file(rom, RomFileCategory.GAME)
    _hide(rom.id, viewer_user.id)

    executed_statements.clear()
    response = client.get(
        f"/api/roms/{rom_file.id}/files", headers=_auth(viewer_access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    _rom_lookup(executed_statements, VISIBILITY_LOOKUP)


def test_hidden_rom_file_content_resolves_the_rom_without_the_related_load(
    client: TestClient,
    viewer_access_token: str,
    viewer_user: User,
    rom: Rom,
    executed_statements: list[str],
) -> None:
    rom_file = _add_file(rom, RomFileCategory.GAME)
    _hide(rom.id, viewer_user.id)

    executed_statements.clear()
    response = client.get(
        f"/api/roms/{rom_file.id}/files/content/bulk.bin",
        headers=_auth(viewer_access_token),
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    _rom_lookup(executed_statements, VISIBILITY_LOOKUP)
