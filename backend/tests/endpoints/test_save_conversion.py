"""GET and POST /api/saves/{id}/content with a core, with sigil itself mocked."""

import io
import json
import zipfile
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_platform, make_rom, make_save

from adapters.services.sigil import SigilGame
from adapters.services.sigil_restore import (
    ContainerMismatch,
    RefusalCode,
    RestoredSave,
    RestoreProfile,
    SharedContainerRequired,
    SigilRefusal,
)
from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_rom_handler,
    db_save_handler,
    db_snapshot_handler,
)
from handler.database.base_handler import sync_session
from handler.filesystem import fs_asset_handler
from handler.snapshots.file_key import FileKey
from models.assets import Save, SaveFormat, SaveShape
from models.device import Device
from models.permission import HiddenEntity, PermEntity
from models.rom import Rom, RomFile
from models.user import User
from utils.zip_cache import ensure_zipfile_writable

UNIT = b"stored unit"
GAME = SigilGame(result=SimpleNamespace(platform="psx"), game_ids=("SLUS-01041",))


@pytest.fixture(autouse=True)
def assets(_isolated_assets_dir: Path) -> Path:
    return _isolated_assets_dir


def _stored(save: Save, data: bytes = UNIT) -> Save:
    path = fs_asset_handler.validate_path(save.full_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return save


def _neutral_gba_unit() -> bytes:
    ensure_zipfile_writable()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("save.sram", b"battery")
        zf.writestr("clock.rtc", b"clock")
    return buffer.getvalue()


def _rom_on(slug: str, name: str, user: User) -> Rom:
    rom = make_rom(make_platform(slug), name, fs_extension="cue")
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)
    return rom


@pytest.fixture
def psx_rom(admin_user: User) -> Rom:
    rom = _rom_on("psx", "Chrono Cross (USA)", admin_user)
    for file_name in ("Chrono Cross (USA).bin", "Chrono Cross (USA).cue"):
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=file_name,
                file_path=rom.fs_path,
                file_size_bytes=10,
            )
        )
    return rom


@pytest.fixture
def psx_save(psx_rom: Rom, admin_user: User) -> Save:
    return _stored(make_save(psx_rom, admin_user, "Chrono Cross (USA).srm"))


@pytest.fixture
def device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(id="conversion-device", user_id=admin_user.id, name="Handheld")
    )


@pytest.fixture
def stored_game() -> Iterator[mock.Mock]:
    with mock.patch(
        "handler.snapshots.restore.SigilService.stored_game", return_value=GAME
    ) as patched:
        yield patched


@pytest.fixture
def restore() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "endpoints.saves.restore_per_game",
        new=mock.AsyncMock(
            return_value=RestoredSave({"memcards/Chrono Cross (USA)_1.mcd": b"card"})
        ),
    ) as patched:
        yield patched


@pytest.fixture
def merge() -> Iterator[mock.AsyncMock]:
    with mock.patch(
        "endpoints.saves.merge_into_container",
        new=mock.AsyncMock(return_value=RestoredSave({"pcsx-card1.mcd": b"merged"})),
    ) as patched:
        yield patched


def _awaited_args(patched: mock.AsyncMock) -> tuple[Any, ...]:
    awaited = patched.await_args
    assert awaited is not None
    return tuple(awaited.args)


def _get(client: TestClient, save: Save, headers: dict[str, str], query: str = ""):
    return client.get(f"/api/saves/{save.id}/content?{query}", headers=headers)


def _post(
    client: TestClient,
    save: Save,
    headers: dict[str, str],
    request: dict[str, object] | str | None = None,
    container: bytes | None = b"card bytes",
    query: str = "",
):
    if request is None:
        request = {"core": "pcsx_rearmed", "container_path": "pcsx-card1.mcd"}
    data = {"request": request if isinstance(request, str) else json.dumps(request)}
    files = {"container": ("card.mcd", container)} if container is not None else None
    return client.post(
        f"/api/saves/{save.id}/content?{query}",
        headers=headers,
        data=data,
        files=files,
    )


class TestGetWithCore:
    def test_options_split_on_the_first_colon_and_companions_repeat(
        self,
        client,
        headers,
        psx_rom: Rom,
        psx_save: Save,
        admin_user: User,
        stored_game,
        restore,
    ):
        prequel = _stored(make_save(psx_rom, admin_user, "Prequel.srm"), b"prequel")
        sequel = _stored(make_save(psx_rom, admin_user, "Sequel.srm"), b"sequel")

        response = _get(
            client,
            psx_save,
            headers,
            "core=duckstation&option=Card1Type:PerGame&option=path:a:b"
            f"&option=empty:&profile=p1&companion={prequel.id}&companion={sequel.id}",
        )

        assert response.status_code == status.HTTP_200_OK
        unit, game, target, companions = _awaited_args(restore)
        assert unit == UNIT
        assert game is GAME
        assert target.core == "duckstation"
        assert target.options == {"Card1Type": "PerGame", "path": "a:b", "empty": ""}
        assert target.profile == "p1"
        assert [c.unit for c in companions] == [b"prequel", b"sequel"]
        assert [c.game_ids for c in companions] == [GAME.game_ids] * 2

    @pytest.mark.parametrize("option", ["Card1Type", ":PerGame"])
    def test_an_option_without_a_key_and_value_is_refused(
        self, client, headers, psx_save: Save, stored_game, restore, option: str
    ):
        response = _get(client, psx_save, headers, f"core=duckstation&option={option}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        restore.assert_not_awaited()

    def test_without_core_the_stored_file_is_served(
        self, client, headers, psx_save: Save, restore
    ):
        response = _get(client, psx_save, headers, "option=Card1Type:PerGame")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == UNIT
        assert "x-save-path" not in response.headers
        restore.assert_not_awaited()

    def test_the_content_path_is_the_roms_loader_file(
        self, client, headers, psx_save: Save, stored_game, restore
    ):
        _get(client, psx_save, headers, "core=duckstation")

        assert _awaited_args(restore)[2].content_path == "Chrono Cross (USA).cue"

    def test_the_content_path_is_the_saves_channel_file(
        self,
        client,
        headers,
        psx_rom: Rom,
        psx_save: Save,
        admin_user: User,
        stored_game,
        restore,
    ):
        disc = next(
            f
            for f in db_rom_handler.rom_files_for_rom_id(psx_rom.id)
            if f.file_name.endswith(".bin")
        )
        channel = db_snapshot_handler.add_channel(
            FileKey.of_file(disc).new_channel(
                admin_user.id, psx_rom.id, psx_rom.platform_id, "default"
            )
        )
        db_save_handler.update_save(psx_save.id, {"channel_id": channel.id})

        _get(client, psx_save, headers, "core=duckstation")

        assert _awaited_args(restore)[2].content_path == "Chrono Cross (USA).bin"

    @pytest.mark.parametrize("slug", ["nes", "snes", "genesis", "gba", "nds"])
    def test_a_platform_without_a_converter_serves_the_stored_file(
        self, client, headers, admin_user: User, restore, slug: str
    ):
        save = _stored(
            make_save(_rom_on(slug, "Game", admin_user), admin_user, "g.srm")
        )

        response = _get(client, save, headers, "core=mesen")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == UNIT
        restore.assert_not_awaited()

    def test_a_neutral_single_unit_without_a_converter_serves_the_stored_file(
        self, client, headers, admin_user: User, restore
    ):
        save = _stored(
            make_save(
                _rom_on("gba", "Game", admin_user),
                admin_user,
                "save.sram",
                shape=SaveShape.SINGLE,
                format=SaveFormat.NEUTRAL,
            )
        )

        response = _get(client, save, headers, "core=mgba")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == UNIT
        restore.assert_not_awaited()

    @pytest.mark.parametrize("shape", [SaveShape.MULTI, SaveShape.FOLDER])
    def test_a_unit_archive_without_a_converter_is_refused(
        self, client, headers, admin_user: User, restore, shape: SaveShape
    ):
        save = _stored(
            make_save(
                _rom_on("gba", "Game", admin_user),
                admin_user,
                "save.zip",
                shape=shape,
                format=SaveFormat.NEUTRAL,
            ),
            _neutral_gba_unit(),
        )

        response = _get(client, save, headers, "core=mgba")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "gba" in response.json()["detail"]
        restore.assert_not_awaited()

    def test_a_wii_save_converts_for_dolphin(
        self, client, headers, admin_user: User, stored_game, restore
    ):
        save = _stored(
            make_save(_rom_on("wii", "Game", admin_user), admin_user, "g.zip")
        )

        response = _get(client, save, headers, "core=dolphin")

        assert response.status_code == status.HTTP_200_OK
        assert _awaited_args(restore)[2].core == "dolphin"

    @pytest.mark.parametrize("slug", ["neogeoaes", "turbografx-cd", "unknown"])
    def test_a_platform_sigil_does_not_sync_is_refused(
        self, client, headers, admin_user: User, restore, slug: str
    ):
        save = _stored(
            make_save(_rom_on(slug, "Game", admin_user), admin_user, "g.sav")
        )

        response = _get(client, save, headers, "core=dolphin")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert slug in response.json()["detail"]
        restore.assert_not_awaited()

    def test_without_the_binding_conversion_is_unavailable(
        self, client, headers, psx_save: Save, restore
    ):
        with mock.patch(
            "handler.snapshots.restore.SigilService.stored_game", return_value=None
        ):
            response = _get(client, psx_save, headers, "core=duckstation")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        restore.assert_not_awaited()

    def test_a_shared_target_names_the_container_to_post(
        self, client, headers, psx_save: Save, stored_game, restore
    ):
        restore.side_effect = SharedContainerRequired("pcsx-card1.mcd")

        response = _get(client, psx_save, headers, "core=pcsx_rearmed")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert detail["error"] == "SHARED_CONTAINER"
        assert detail["container_path"] == "pcsx-card1.mcd"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            (RefusalCode.UNCOLLECTED, status.HTTP_409_CONFLICT),
            (RefusalCode.CONFLICT, status.HTTP_409_CONFLICT),
            (RefusalCode.EXISTS, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (RefusalCode.DAMAGED, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (RefusalCode.REGION, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (RefusalCode.NO_SPACE, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (RefusalCode.NOT_FOUND, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (RefusalCode.UNSUPPORTED_FORMAT, status.HTTP_422_UNPROCESSABLE_CONTENT),
            (RefusalCode.NO_TARGET, status.HTTP_400_BAD_REQUEST),
            (RefusalCode.AMBIGUOUS, status.HTTP_400_BAD_REQUEST),
            (RefusalCode.INVALID_ARG, status.HTTP_400_BAD_REQUEST),
            (RefusalCode.IO, status.HTTP_500_INTERNAL_SERVER_ERROR),
            (RefusalCode.OTHER, status.HTTP_500_INTERNAL_SERVER_ERROR),
        ],
    )
    def test_each_refusal_maps_to_its_status(
        self,
        client,
        headers,
        psx_save: Save,
        device: Device,
        stored_game,
        restore,
        code: RefusalCode,
        expected: int,
    ):
        restore.side_effect = SigilRefusal(code, "refused", "the problem")

        response = _get(
            client, psx_save, headers, f"core=pcsx_rearmed&device_id={device.id}"
        )

        assert response.status_code == expected
        assert response.json()["detail"]["error"] == code.value
        assert response.json()["detail"]["problem"] == "the problem"
        assert (
            db_device_save_sync_handler.get_sync(
                device_id=device.id, save_id=psx_save.id
            )
            is None
        )

    def test_an_ambiguous_profile_lists_the_profiles(
        self, client, headers, psx_save: Save, stored_game, restore
    ):
        restore.side_effect = SigilRefusal(
            RefusalCode.AMBIGUOUS,
            "ambiguous",
            "A Eden\nB citron",
            (RestoreProfile("A", "Eden"), RestoreProfile("B", "citron")),
        )

        response = _get(client, psx_save, headers, "core=eden")

        assert response.json()["detail"]["profiles"] == [
            {"id": "A", "name": "Eden"},
            {"id": "B", "name": "citron"},
        ]

    def test_one_file_comes_back_raw_with_its_save_path(
        self, client, headers, psx_save: Save, stored_game, restore
    ):
        response = _get(client, psx_save, headers, "core=duckstation")

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"card"
        assert (
            response.headers["x-save-path"]
            == "memcards/Chrono%20Cross%20%28USA%29_1.mcd"
        )
        assert 'filename="Chrono%20Cross%20%28USA%29_1.mcd"' in (
            response.headers["content-disposition"]
        )

    def test_several_files_come_back_as_a_zip_of_save_paths(
        self, client, headers, psx_save: Save, stored_game, restore
    ):
        restore.return_value = RestoredSave({"game.srm": b"ram", "game.rtc": b"clock"})

        response = _get(client, psx_save, headers, "core=gambatte")

        assert response.status_code == status.HTTP_200_OK
        assert "x-save-path" not in response.headers
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            assert {name: zf.read(name) for name in zf.namelist()} == {
                "game.rtc": b"clock",
                "game.srm": b"ram",
            }

    def test_a_converted_download_records_the_device_sync(
        self, client, headers, psx_save: Save, device: Device, stored_game, restore
    ):
        response = _get(
            client, psx_save, headers, f"core=duckstation&device_id={device.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        sync = db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=psx_save.id
        )
        assert sync is not None
        assert sync.last_sync_server_hash == psx_save.content_hash


LAYOUT = SimpleNamespace(
    id="genesis_plus_gx",
    platform="segacd",
    options=(
        SimpleNamespace(
            key="genesis_plus_gx_region_detect",
            values=("auto", "ntsc-u", "pal", "ntsc-j"),
            default="auto",
        ),
    ),
    region_option="genesis_plus_gx_region_detect",
    profiles=False,
    needs_existing=False,
)


class TestLayouts:
    @pytest.fixture
    def layouts(self) -> Iterator[mock.Mock]:
        with mock.patch(
            "endpoints.saves.restore_layouts", return_value=(LAYOUT,)
        ) as patched:
            yield patched

    def test_the_rows_come_back_for_sigils_platform(self, client, headers, layouts):
        with mock.patch("endpoints.saves.SigilService.is_enabled", return_value=True):
            response = client.get("/api/saves/layouts?platform=segacd", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        layouts.assert_called_once_with("segacd")
        assert response.json() == [
            {
                "id": "genesis_plus_gx",
                "platform": "segacd",
                "options": [
                    {
                        "key": "genesis_plus_gx_region_detect",
                        "values": ["auto", "ntsc-u", "pal", "ntsc-j"],
                        "default": "auto",
                    }
                ],
                "region_option": "genesis_plus_gx_region_detect",
                "profiles": False,
                "needs_existing": False,
            }
        ]

    def test_a_romm_slug_maps_to_sigils(self, client, headers, layouts):
        with mock.patch("endpoints.saves.SigilService.is_enabled", return_value=True):
            client.get("/api/saves/layouts?platform=ngc", headers=headers)

        layouts.assert_called_once_with("gamecube")

    @pytest.mark.parametrize("slug", ["snes", "neogeoaes", "unknown"])
    def test_a_platform_sigil_does_not_restore_is_refused(
        self, client, headers, layouts, slug: str
    ):
        response = client.get(f"/api/saves/layouts?platform={slug}", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        layouts.assert_not_called()

    def test_without_the_binding_the_catalog_is_unavailable(
        self, client, headers, layouts
    ):
        with mock.patch("endpoints.saves.SigilService.is_enabled", return_value=False):
            response = client.get("/api/saves/layouts?platform=psx", headers=headers)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        layouts.assert_not_called()

    def test_without_the_platform_it_is_unprocessable(self, client, headers, layouts):
        response = client.get("/api/saves/layouts", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_the_binding_reports_wiis_dolphin_rows(self, client, headers):
        pytest.importorskip("sigil")

        response = client.get("/api/saves/layouts?platform=wii", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        rows = {row["id"]: row for row in response.json()}
        assert response.json()[0]["id"] == "libretro"
        assert rows["dolphin"]["platform"] == "wii"
        assert rows["dolphin_standalone"]["platform"] == "wii"


class TestCompanionVisibility:
    def test_another_users_private_companion_is_not_found(
        self,
        client,
        headers,
        psx_rom: Rom,
        psx_save: Save,
        viewer_user: User,
        stored_game,
        restore,
    ):
        hidden = _stored(make_save(psx_rom, viewer_user, "Theirs.srm"))

        response = _get(
            client, psx_save, headers, f"core=pcsx_rearmed&companion={hidden.id}"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        restore.assert_not_awaited()

    def test_a_public_companion_on_a_hidden_rom_is_not_found(
        self,
        client,
        viewer_access_token: str,
        viewer_user: User,
        admin_user: User,
        stored_game,
        restore,
    ):
        own = _stored(
            make_save(_rom_on("psx", "Sequel", viewer_user), viewer_user, "Mine.srm")
        )
        hidden_rom = _rom_on("psx", "Prequel", admin_user)
        companion = _stored(
            make_save(hidden_rom, admin_user, "Shared.srm", is_public=True)
        )
        with sync_session.begin() as session:
            session.add(
                HiddenEntity(
                    entity=PermEntity.ROMS,
                    entity_id=hidden_rom.id,
                    user_id=viewer_user.id,
                )
            )

        response = _get(
            client,
            own,
            {"Authorization": f"Bearer {viewer_access_token}"},
            f"core=pcsx_rearmed&companion={companion.id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        restore.assert_not_awaited()


class TestPostContainer:
    def test_the_container_merges_and_comes_back_at_its_path(
        self, client, headers, psx_save: Save, device: Device, stored_game, merge
    ):
        response = _post(
            client,
            psx_save,
            headers,
            {
                "core": "pcsx_rearmed",
                "options": {"pcsx_rearmed_memcard1": "shared"},
                "container_path": "pcsx-card1.mcd",
            },
            query=f"device_id={device.id}",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"merged"
        assert response.headers["x-save-path"] == "pcsx-card1.mcd"
        unit, game, target, container_path, container, companions = _awaited_args(merge)
        assert (unit, game, container_path, container) == (
            UNIT,
            GAME,
            "pcsx-card1.mcd",
            b"card bytes",
        )
        assert target.options == {"pcsx_rearmed_memcard1": "shared"}
        assert target.content_path == "Chrono Cross (USA).cue"
        assert companions == []
        assert db_device_save_sync_handler.get_sync(
            device_id=device.id, save_id=psx_save.id
        )

    @pytest.mark.parametrize(
        "container_path",
        [
            "",
            "../Mcd001.ps2",
            "memcards/../../Mcd001.ps2",
            "/etc/passwd",
            "memcards\\Mcd001.ps2",
            "C:Mcd001.ps2",
            "card\x00.mcd",
        ],
    )
    def test_a_container_path_leaving_the_save_root_is_refused(
        self, client, headers, psx_save: Save, stored_game, merge, container_path: str
    ):
        response = _post(
            client,
            psx_save,
            headers,
            {"core": "pcsx_rearmed", "container_path": container_path},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        merge.assert_not_awaited()

    def test_a_container_over_the_card_limit_is_too_large(
        self, client, headers, psx_save: Save, stored_game, merge
    ):
        with mock.patch("endpoints.saves.MEMORY_CARD_MAX_BYTES", 4):
            response = _post(client, psx_save, headers, container=b"12345")

        assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
        merge.assert_not_awaited()

    def test_a_missing_container_part_is_unprocessable(
        self, client, headers, psx_save: Save, stored_game, merge
    ):
        response = _post(client, psx_save, headers, container=None)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        merge.assert_not_awaited()

    @pytest.mark.parametrize(
        "request_part", ["{not json", json.dumps({"core": "pcsx_rearmed"})]
    )
    def test_a_malformed_request_part_is_unprocessable(
        self, client, headers, psx_save: Save, stored_game, merge, request_part: str
    ):
        response = _post(client, psx_save, headers, request_part)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        merge.assert_not_awaited()

    def test_a_restore_into_another_container_is_refused(
        self, client, headers, psx_save: Save, device: Device, stored_game, merge
    ):
        merge.side_effect = ContainerMismatch(
            "scd_E.brm", ("scd_U.brm",), {"genesis_plus_gx_region_detect": None}
        )

        response = _post(
            client,
            psx_save,
            headers,
            {"core": "genesis_plus_gx", "container_path": "scd_E.brm"},
            query=f"device_id={device.id}",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        detail = response.json()["detail"]
        assert detail["error"] == "CONTAINER_MISMATCH"
        assert detail["container_path"] == "scd_E.brm"
        assert detail["written"] == ["scd_U.brm"]
        assert detail["options"] == {"genesis_plus_gx_region_detect": None}
        assert "genesis_plus_gx_region_detect" in detail["message"]
        assert (
            db_device_save_sync_handler.get_sync(
                device_id=device.id, save_id=psx_save.id
            )
            is None
        )

    def test_a_platform_without_a_converter_serves_the_stored_file(
        self, client, headers, admin_user: User, merge
    ):
        save = _stored(
            make_save(_rom_on("snes", "Game", admin_user), admin_user, "g.srm")
        )

        response = _post(client, save, headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.content == UNIT
        merge.assert_not_awaited()

    def test_a_unit_archive_without_a_converter_is_refused(
        self, client, headers, admin_user: User, merge
    ):
        save = _stored(
            make_save(
                _rom_on("gba", "Game", admin_user),
                admin_user,
                "save.zip",
                shape=SaveShape.MULTI,
                format=SaveFormat.NEUTRAL,
            ),
            _neutral_gba_unit(),
        )

        response = _post(client, save, headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        merge.assert_not_awaited()

    def test_another_users_private_save_is_not_found(
        self,
        client,
        viewer_access_token: str,
        psx_save: Save,
        stored_game,
        merge,
    ):
        response = _post(
            client, psx_save, {"Authorization": f"Bearer {viewer_access_token}"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        merge.assert_not_awaited()
