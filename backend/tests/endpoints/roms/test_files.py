from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_file(rom: Rom, name: str, category: RomFileCategory | None) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=name,
            file_path=f"{rom.fs_path}/{rom.fs_name}",
            file_size_bytes=10,
            category=category,
        )
    )


def _make_rom(admin_user: User, platform: Platform) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="media_rom",
            slug="media_rom_slug",
            fs_name="media_rom",
            fs_name_no_tags="media_rom",
            fs_name_no_ext="media_rom",
            fs_extension="",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    return rom


def test_image_file_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "trailer_thumb.png", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/trailer_thumb.png",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("image/png")
    assert r.headers["content-disposition"].startswith("inline")


def test_video_file_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "trailer.mp4", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/trailer.mp4",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("video/mp4")
    assert r.headers["content-disposition"].startswith("inline")


def test_pdf_manual_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "manual.pdf", RomFileCategory.MANUAL)

    r = client.get(
        f"/api/roms/{file.id}/files/content/manual.pdf",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_markdown_manual_served_inline(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "manual.md", RomFileCategory.MANUAL)

    r = client.get(
        f"/api/roms/{file.id}/files/content/manual.md",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.headers["content-disposition"].startswith("inline")
    # nosniff keeps the browser from sniffing the Markdown into HTML.
    assert r.headers["x-content-type-options"] == "nosniff"


def test_non_manual_document_served_as_attachment(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    # A game/extra file that happens to end in .pdf must still download; only
    # manual-category documents are served inline.
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "readme.pdf", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/readme.pdf",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert r.headers["content-disposition"].startswith("attachment")


def test_rom_file_served_as_attachment(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "game.bin", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/game.bin",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert r.headers["content-disposition"].startswith("attachment")


def test_content_type_derived_from_db_not_path_param(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    # A caller must not be able to force an inline image content-type on a
    # non-media file by tacking a fake extension onto the URL path param.
    rom = _make_rom(admin_user, platform)
    file = _add_file(rom, "game.bin", RomFileCategory.GAME)

    r = client.get(
        f"/api/roms/{file.id}/files/content/game.bin.png",
        headers=_auth(access_token),
    )

    assert r.status_code == status.HTTP_200_OK
    assert r.headers["content-type"].startswith("application/octet-stream")
    assert r.headers["content-disposition"].startswith("attachment")
