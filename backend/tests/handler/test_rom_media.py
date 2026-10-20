from pathlib import Path
from typing import Any

import pytest

from handler.filesystem import fs_resource_handler
from handler.rom_media import RomMedia, describe_rom_media
from models.rom import Rom, RomFile


@pytest.fixture
def resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fs_resource_handler, "base_path", tmp_path)
    return tmp_path


def _store(resources: Path, relative_path: str, size: int) -> str:
    target = resources / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * size)
    return relative_path


def _rom(**fields: Any) -> Rom:
    return Rom(id=1, platform_id=1, fs_path="nes/roms", fs_name="Game", **fields)


def _by_path(media: list[RomMedia]) -> dict[str, RomMedia]:
    return {m.path.removeprefix("/assets/romm/resources/"): m for m in media}


def test_rom_slots_are_sized_from_disk(resources: Path) -> None:
    rom = _rom(
        path_cover_l=_store(resources, "roms/1/1/cover/big.png", 300),
        path_cover_s=_store(resources, "roms/1/1/cover/small.png", 100),
        path_manual=_store(resources, "roms/1/1/manual/1.pdf", 900),
        path_screenshots=[
            _store(resources, "roms/1/1/screenshots/0.jpg", 50),
            _store(resources, "roms/1/1/screenshots/1.JPG", 60),
        ],
    )

    media = describe_rom_media(rom, [])

    assert [(m.type, m.source, m.size_bytes, m.format, m.index) for m in media] == [
        ("cover_large", "romm", 300, "png", None),
        ("cover_small", "romm", 100, "png", None),
        ("manual", "romm", 900, "pdf", None),
        ("screenshot", "romm", 50, "jpg", 0),
        ("screenshot", "romm", 60, "jpg", 1),
    ]
    assert media[0].path == "/assets/romm/resources/roms/1/1/cover/big.png"


def test_higher_priority_provider_shadows_the_same_kind(resources: Path) -> None:
    rom = _rom(
        ss_metadata={"box3d_path": _store(resources, "roms/1/1/box3d/ss.png", 10)},
        gamelist_metadata={
            "box3d_path": _store(resources, "roms/1/1/box3d/gl.png", 20),
            "marquee_path": _store(resources, "roms/1/1/marquee/gl.png", 30),
        },
        launchbox_metadata={
            "box3d_path": _store(resources, "roms/1/1/box3d/lb.png", 40)
        },
    )

    media = _by_path(describe_rom_media(rom, []))

    assert {path: (m.source, m.shadowed) for path, m in media.items()} == {
        "roms/1/1/box3d/ss.png": ("ss", False),
        "roms/1/1/box3d/gl.png": ("gamelist", True),
        "roms/1/1/box3d/lb.png": ("launchbox", True),
        "roms/1/1/marquee/gl.png": ("gamelist", False),
    }


def test_a_shared_path_is_listed_once_for_its_first_provider(resources: Path) -> None:
    shared = _store(resources, "roms/1/1/fanart/fanart.jpg", 10)
    rom = _rom(
        ss_metadata={"fanart_path": shared},
        gamelist_metadata={"fanart_path": shared},
    )

    media = describe_rom_media(rom, [])

    assert [(m.source, m.shadowed) for m in media] == [("ss", False)]


def test_each_disc_resolves_on_its_own(resources: Path) -> None:
    rom = _rom(
        ss_metadata={
            "physical_path": _store(resources, "roms/1/1/physical/physical.png", 10),
            "physical_disc": 1,
            "physical_extra_discs": [
                {
                    "disc": 2,
                    "path": _store(
                        resources, "roms/1/1/physical/physical_disc2.png", 20
                    ),
                    "url": None,
                }
            ],
        },
        gamelist_metadata={
            "physical_path": _store(resources, "roms/1/1/physical/gl.png", 30)
        },
    )

    media = _by_path(describe_rom_media(rom, []))

    assert {path: (m.disc, m.shadowed) for path, m in media.items()} == {
        "roms/1/1/physical/physical.png": (1, False),
        "roms/1/1/physical/physical_disc2.png": (2, False),
        "roms/1/1/physical/gl.png": (None, True),
    }


def test_recorded_paths_without_a_file_are_left_out(resources: Path) -> None:
    _store(resources, "roms/1/1/logo", 0)
    (resources / "roms/1/1/logo").unlink()
    (resources / "roms/1/1/logo").mkdir()
    rom = _rom(
        path_cover_l="roms/1/1/cover/big.png",
        ss_metadata={
            "logo_path": "roms/1/1/logo",
            "bezel_path": "../outside.png",
        },
    )

    assert describe_rom_media(rom, []) == []


def test_library_images_and_videos_are_listed_from_their_rows(
    resources: Path,
) -> None:
    rom = _rom()

    def file(file_id: int, file_name: str, **fields: Any) -> RomFile:
        return RomFile(
            id=file_id,
            rom=rom,
            file_name=file_name,
            file_path=fields.pop("file_path", "nes/roms/Game"),
            file_size_bytes=file_id * 1000,
            missing_from_fs=fields.pop("missing_from_fs", False),
            **fields,
        )

    files = [
        file(1, "Box Art.PNG", md5_hash="abc"),
        file(2, "trailer.mp4"),
        file(3, "game.nes"),
        file(4, "nested.png", file_path="nes/roms/Game/extras"),
        file(5, "gone.png", missing_from_fs=True),
    ]

    media = describe_rom_media(rom, files)

    assert media == [
        RomMedia(
            type="image",
            source="library",
            path="/api/roms/1/files/content/Box%20Art.PNG",
            size_bytes=1000,
            format="png",
            file_id=1,
            md5="abc",
        ),
        RomMedia(
            type="video",
            source="library",
            path="/api/roms/2/files/content/trailer.mp4",
            size_bytes=2000,
            format="mp4",
            file_id=2,
        ),
    ]
