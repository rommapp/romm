"""A whole shared memory card pushed as a game's save keeps that game's saves alone.

Tests that split cards run the real sigil binding and skip where it isn't built.
"""

import hashlib
import json
from collections.abc import Iterator
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_platform, make_rom
from tests.sigil_cards import (
    PS1_BLOCK,
    card_entries,
    gamecube_card,
    gci,
    ps1_card,
    ps2_card,
    ps2_folder_unit,
    saturn_volume,
)

from adapters.services.sigil import SigilGame
from adapters.services.sigil_card import CardSplitError
from handler.database import db_rom_handler, db_snapshot_handler
from models.rom import RomFile
from models.user import User

CROSS = "BASLUSP01041CROSS"
CROSS_DISC_2 = "BASLUSP01080CROSS"
OTHER = "BASLUS-00067OTHER"
THIRD = "BASLUS-00068THIRD"

pytestmark = pytest.mark.usefixtures("_isolated_assets_dir")


def md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


@pytest.fixture
def binding() -> ModuleType:
    module: ModuleType = pytest.importorskip("sigil")
    return module


def _game_rom(
    user: User, slug: str, name: str, discs: list[tuple[str, str]], **identity: str
) -> RomFile:
    """A ROM whose files are each (file name, title id), returning the first."""
    rom = make_rom(make_platform(slug), name, fs_extension="cue", **identity)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)
    files = [
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=file_name,
                file_path=rom.fs_path,
                file_size_bytes=10,
                sha1_hash=hashlib.sha1(file_name.encode()).hexdigest(),
                title_id=title_id,
                sigil_features=0,
            )
        )
        for file_name, title_id in discs
    ]
    return files[0]


@pytest.fixture
def cross_file(admin_user: User) -> RomFile:
    return _game_rom(
        admin_user,
        "psx",
        "Chrono Cross (USA)",
        [
            ("Chrono Cross (USA) (Disc 1).cue", "SLUS-01041"),
            ("Chrono Cross (USA) (Disc 2).cue", "SLUS-01080"),
        ],
        title_id="SLUS-01041",
        save_target="SLUS-01041",
    )


def native(data: bytes) -> dict[str, str]:
    return {"hash": md5(data), "shape": "SINGLE", "format": "native"}


def push(
    client: TestClient,
    headers: dict[str, str],
    rom_file: RomFile,
    card: bytes | None,
    *,
    declared: bytes | None = None,
    previous: dict[str, Any] | None = None,
    label: str = "default",
    file_name: str = "shared_card_1.mcd",
):
    body: dict[str, Any] = {
        "rom_file_id": rom_file.id,
        "expected_current_id": previous["id"] if previous else None,
        "save": native(declared if declared is not None else card or b""),
        "emulator": "duckstation",
    }
    if previous:
        body["channel_id"] = previous["channel"]["id"]
    else:
        body["label"] = label
    return client.post(
        "/api/snapshots",
        data={"manifest": json.dumps(body)},
        files={"save": (file_name, card)} if card is not None else {"_": ("", b"")},
        headers=headers,
    )


def created(response) -> dict[str, Any]:
    assert response.status_code == status.HTTP_201_CREATED, response.text
    body: dict[str, Any] = response.json()
    return body


def stored(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> bytes:
    response = client.get(body["save"]["download_path"], headers=headers)
    assert response.status_code == status.HTTP_200_OK
    content: bytes = response.content
    return content


def whole_card(cross_fill: int = 0x11, other_fill: int = 0x33) -> bytes:
    return ps1_card(
        [(CROSS, 2), (OTHER, 1)], {1: cross_fill, 2: cross_fill, 3: other_fill}
    )


def test_a_whole_card_is_stored_as_the_games_saves_alone(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = whole_card()

    body = created(push(client, headers, cross_file, card))
    unit = stored(client, headers, body)

    assert card_entries(binding, unit) == {CROSS: "SLUS-01041"}
    assert body["save"]["format"] == "neutral"
    assert body["save"]["shape"] == "SINGLE"
    assert body["save"]["content_hash"] == md5(unit)
    assert body["save"]["content_hash"] != md5(card)
    assert body["save"]["file_name"].startswith("Chrono Cross (USA) (Disc 1)")


def test_another_games_change_on_the_card_leaves_the_channel_unchanged(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    first = created(push(client, headers, cross_file, whole_card()))

    again = push(
        client, headers, cross_file, whole_card(other_fill=0x44), previous=first
    )
    channel = db_snapshot_handler.get_channel(first["channel"]["id"])
    history = client.get(
        "/api/snapshots",
        params={"channel_id": first["channel"]["id"]},
        headers=headers,
    ).json()

    assert again.status_code == status.HTTP_200_OK, again.text
    assert again.json()["id"] == first["id"]
    assert channel is not None and channel.current_snapshot_id == first["id"]
    assert [snapshot["id"] for snapshot in history] == [first["id"]]


def test_the_games_change_on_the_card_makes_a_snapshot(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    first = created(push(client, headers, cross_file, whole_card()))

    second = created(
        push(client, headers, cross_file, whole_card(cross_fill=0x22), previous=first)
    )

    assert second["id"] != first["id"]
    assert second["channel"]["current_snapshot_id"] == second["id"]
    assert stored(client, headers, second)[PS1_BLOCK : PS1_BLOCK + 1] == b"\x22"


def test_a_per_game_card_is_stored_as_sent(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = ps1_card([(CROSS, 2)], {1: 0x11, 2: 0x11})

    body = created(push(client, headers, cross_file, card, file_name="game.srm"))

    assert stored(client, headers, body) == card
    assert body["save"]["format"] == "native"
    assert body["save"]["content_hash"] == md5(card)


def test_a_card_with_none_of_the_games_saves_is_stored_as_sent(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = ps1_card([(OTHER, 1)], {1: 0x33})

    body = created(push(client, headers, cross_file, card))

    assert stored(client, headers, body) == card
    assert body["save"]["format"] == "native"


def test_a_card_whose_bytes_miss_the_declared_hash_is_refused(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    response = push(
        client, headers, cross_file, whole_card(), declared=whole_card(0x99)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "manifest" in response.json()["detail"]


def test_naming_the_whole_cards_hash_alone_asks_for_the_card(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = whole_card()
    first = created(push(client, headers, cross_file, card))

    response = push(client, headers, cross_file, None, declared=card, previous=first)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"missing": ["save"]}


def test_without_sigil_the_card_is_stored_as_sent(
    client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = whole_card()

    with mock.patch("adapters.services.sigil.sigil", None):
        body = created(push(client, headers, cross_file, card))

    assert stored(client, headers, body) == card
    assert body["save"]["format"] == "native"


@pytest.fixture
def failing_split() -> Iterator[mock.AsyncMock]:
    game = SigilGame(result=SimpleNamespace(platform="psx"), game_ids=("SLUS-01041",))
    with (
        mock.patch(
            "handler.snapshots.shared_card.SigilService.stored_game",
            return_value=game,
        ),
        mock.patch(
            "handler.snapshots.shared_card.game_card",
            new=mock.AsyncMock(side_effect=CardSplitError("the card is damaged")),
        ) as patched,
    ):
        yield patched


def test_a_sigil_failure_stores_the_card_as_sent(
    client: TestClient,
    headers: dict[str, str],
    cross_file: RomFile,
    failing_split: mock.AsyncMock,
):
    card = whole_card()

    body = created(push(client, headers, cross_file, card))

    failing_split.assert_awaited_once()
    assert stored(client, headers, body) == card
    assert body["save"]["format"] == "native"


def test_a_save_under_a_later_discs_serial_is_kept_as_the_games(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = ps1_card([(CROSS_DISC_2, 1), (OTHER, 1)], {1: 0x22, 2: 0x33})

    body = created(push(client, headers, cross_file, card))

    assert card_entries(binding, stored(client, headers, body)) == {
        CROSS_DISC_2: "SLUS-01080"
    }


def test_a_whole_ps2_card_is_stored_as_the_games_saves_alone(
    binding, client: TestClient, headers: dict[str, str], admin_user: User
):
    rom_file = _game_rom(
        admin_user,
        "ps2",
        "Ace Combat 04 (USA)",
        [("Ace Combat 04 (USA).iso", "SLUS-20152")],
        title_id="SLUS-20152",
        save_target="BASLUS-20152",
    )
    ace = binding.SigilResult.persisted("ps2", "SLUS-20152", "BASLUS-20152", 0)
    norrath = binding.SigilResult.persisted("ps2", "SLUS-20565", "BASLUS-20565", 0)

    def card(norrath_fill: int) -> bytes:
        return ps2_card(
            binding,
            [
                (ace, ps2_folder_unit("BASLUS-20152AC04", b"\x11" * 3000)),
                (
                    norrath,
                    ps2_folder_unit("BASLUS-20565", bytes([norrath_fill]) * 2000),
                ),
            ],
        )

    first = created(push(client, headers, rom_file, card(0x22), file_name="Mcd001.ps2"))
    again = push(
        client, headers, rom_file, card(0x23), previous=first, file_name="Mcd001.ps2"
    )

    assert card_entries(binding, stored(client, headers, first)) == {
        "BASLUS-20152AC04": "SLUS-20152"
    }
    assert first["save"]["format"] == "neutral"
    assert again.status_code == status.HTTP_200_OK, again.text
    assert again.json()["id"] == first["id"]


def test_a_gamecube_raw_card_is_stored_as_the_games_save_file(
    binding, client: TestClient, headers: dict[str, str], admin_user: User
):
    rom_file = _game_rom(
        admin_user,
        "ngc",
        "Need for Speed Underground 2 (USA)",
        [("Need for Speed Underground 2 (USA).iso", "47554745")],
        title_id="47554745",
        save_target="GUGE",
    )
    nfsu2 = binding.SigilResult.persisted("gamecube", "47554745", "GUGE", 0)
    sunshine = binding.SigilResult.persisted("gamecube", "474D5345", "GMSE", 0)
    save = gci("GUGE", "69", "NFSU2", 2, 0x11)
    card = gamecube_card(
        binding,
        [(nfsu2, save), (sunshine, gci("GMSE", "01", "super_mario_sunshine", 1, 0x22))],
    )

    body = created(
        push(client, headers, rom_file, card, file_name="MemoryCardA.USA.raw")
    )
    unit = stored(client, headers, body)

    assert body["save"]["format"] == "neutral"
    assert body["save"]["file_name"].endswith(".gci")
    assert unit[:6] == b"GUGE69"
    assert unit[64:] == save[64:]


def test_a_saturn_volume_is_stored_as_sent(
    client: TestClient, headers: dict[str, str], admin_user: User
):
    rom_file = _game_rom(
        admin_user, "saturn", "Rayman (USA)", [("Rayman (USA).cue", "")]
    )
    volume = saturn_volume([("RAYMAN_NTS", 0x11), ("THREE_DIRTY", 0x33)])

    body = created(push(client, headers, rom_file, volume, file_name="backup.bkr"))

    assert stored(client, headers, body) == volume
    assert body["save"]["format"] == "native"


def test_a_legacy_slot_upload_of_a_whole_card_is_stored_as_sent(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    card = whole_card()

    response = client.post(
        "/api/saves",
        params={
            "rom_id": cross_file.rom_id,
            "emulator": "duckstation",
            "slot": "default",
        },
        files={"saveFile": ("shared_card_1.mcd", card)},
        headers=headers,
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    content = client.get(f"/api/saves/{response.json()['id']}/content", headers=headers)

    assert content.content == card


def test_another_user_reading_a_shared_channel_gets_the_games_saves_alone(
    binding,
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    cross_file: RomFile,
):
    body = created(push(client, headers, cross_file, whole_card()))
    client.patch(
        f"/api/channels/{body['channel']['id']}",
        json={"is_public": True},
        headers=headers,
    )

    seen = client.get(f"/api/snapshots/{body['id']}", headers=editor_headers).json()
    content = stored(client, editor_headers, seen)

    assert card_entries(binding, content) == {CROSS: "SLUS-01041"}


def test_a_split_save_converts_for_a_per_game_card(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    body = created(push(client, headers, cross_file, whole_card()))

    response = client.get(
        f"/api/saves/{body['save']['id']}/content",
        params={"core": "duckstation", "option": "Card1Type:PerGame"},
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.headers["X-Save-Path"] == "memcards/SLUS-01041_1.mcd"
    assert card_entries(binding, response.content) == {CROSS: "SLUS-01041"}


def test_a_split_save_merges_into_a_card_keeping_the_other_games_save(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    body = created(push(client, headers, cross_file, whole_card(cross_fill=0x11)))
    client_card = ps1_card([(CROSS, 2), (THIRD, 1)], {1: 0x55, 2: 0x55, 3: 0x66})

    response = client.post(
        f"/api/saves/{body['save']['id']}/content",
        data={
            "request": json.dumps(
                {
                    "core": "pcsx_rearmed",
                    "options": {"pcsx_rearmed_memcard1": "shared"},
                    "container_path": "pcsx-card1.mcd",
                }
            )
        },
        files={"container": ("pcsx-card1.mcd", client_card)},
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert card_entries(binding, response.content) == {
        CROSS: "SLUS-01041",
        THIRD: "SLUS-00068",
    }
    assert bytes([0x11]) * PS1_BLOCK in response.content
    assert bytes([0x55]) * PS1_BLOCK not in response.content


def test_two_cards_with_the_same_saves_of_the_game_share_one_stored_save(
    binding, client: TestClient, headers: dict[str, str], cross_file: RomFile
):
    first = created(push(client, headers, cross_file, whole_card(), label="one"))
    other_card = ps1_card([(THIRD, 3), (CROSS, 2)], {1: 0x44, 4: 0x11, 5: 0x11})

    second = created(push(client, headers, cross_file, other_card, label="two"))

    assert second["channel"]["id"] != first["channel"]["id"]
    assert second["save"]["content_hash"] == first["save"]["content_hash"]
    assert second["save"]["id"] == first["save"]["id"]
