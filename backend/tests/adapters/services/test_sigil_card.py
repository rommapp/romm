"""Splitting a game's saves off a shared card through the real sigil binding;
every test skips where it isn't built."""

from types import ModuleType

import pytest
from tests.sigil_cards import (
    GAMECUBE_BLOCK,
    PS1_BLOCK,
    card_entries,
    gamecube_card,
    gci,
    ps1_card,
    ps2_card,
    ps2_folder_unit,
)

from adapters.services.sigil import SigilGame
from adapters.services.sigil_card import (
    CardContents,
    CardSplitError,
    game_card,
)

CROSS = "BASLUSP01041CROSS"
CROSS_DISC_2 = "BASLUSP01080CROSS"
OTHER = "BASLUS-00067OTHER"
THIRD = "BASLUS-00068THIRD"


@pytest.fixture
def binding() -> ModuleType:
    module: ModuleType = pytest.importorskip("sigil")
    return module


def cross(binding: ModuleType) -> SigilGame:
    return SigilGame(
        result=binding.SigilResult.persisted("psx", "SLUS-01041", "SLUS-01041", 0),
        game_ids=("SLUS-01041", "SLUS-01080"),
    )


@pytest.mark.asyncio
async def test_a_card_with_another_games_save_gives_the_games_saves_alone(binding):
    card = ps1_card([(CROSS, 2), (OTHER, 1)], {1: 0x11, 2: 0x11, 3: 0x33})

    found = await game_card(card, cross(binding), "Chrono Cross (USA).cue")

    assert found.contents == CardContents.OTHER_GAMES_TOO
    assert found.saves_on_card == 2
    assert found.shape == "single"
    assert found.artifact == "Chrono Cross (USA).mcd"
    assert found.unit is not None
    assert card_entries(binding, found.unit) == {CROSS: "SLUS-01041"}
    assert found.unit[PS1_BLOCK : 3 * PS1_BLOCK] == bytes([0x11]) * 2 * PS1_BLOCK


@pytest.mark.asyncio
async def test_the_same_saves_on_two_different_cards_give_one_unit(binding):
    first = ps1_card([(CROSS, 2), (OTHER, 1)], {1: 0x11, 2: 0x11, 3: 0x33})
    second = ps1_card([(THIRD, 3), (CROSS, 2)], {1: 0x44, 4: 0x11, 5: 0x11})

    one = await game_card(first, cross(binding), "Chrono Cross (USA).cue")
    two = await game_card(second, cross(binding), "Chrono Cross (USA).cue")

    assert one.unit is not None
    assert one.unit == two.unit


@pytest.mark.asyncio
async def test_a_card_of_the_games_saves_alone_stays_as_it_is(binding):
    card = ps1_card([(CROSS, 2)], {1: 0x11, 2: 0x11})

    found = await game_card(card, cross(binding), "Chrono Cross (USA).cue")

    assert found.contents == CardContents.ONLY_THE_GAMES
    assert found.unit is None


@pytest.mark.asyncio
async def test_a_save_under_a_later_discs_serial_is_the_games(binding):
    card = ps1_card([(CROSS_DISC_2, 1), (OTHER, 1)], {1: 0x22, 2: 0x33})

    found = await game_card(card, cross(binding), "Chrono Cross (USA).cue")

    assert found.contents == CardContents.OTHER_GAMES_TOO
    assert found.unit is not None
    assert card_entries(binding, found.unit) == {CROSS_DISC_2: "SLUS-01080"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "card", [ps1_card([(OTHER, 1)]), ps1_card([])], ids=["another game's", "empty"]
)
async def test_a_card_with_none_of_the_games_saves_stays_as_it_is(binding, card):
    found = await game_card(card, cross(binding), "Chrono Cross (USA).cue")

    assert found.contents == CardContents.NONE_OF_THE_GAMES
    assert found.unit is None


@pytest.mark.asyncio
async def test_bytes_that_are_no_card_are_left_alone(binding):
    found = await game_card(b"not a card", cross(binding), "Chrono Cross (USA).cue")

    assert found.contents == CardContents.NOT_A_CARD


@pytest.mark.asyncio
async def test_a_sigil_failure_is_reported(binding, monkeypatch):
    def refuse(*_args, **_kwargs):
        raise binding.SigilDamagedError(0, "damaged")

    monkeypatch.setattr(binding, "collect", refuse)
    card = ps1_card([(CROSS, 1), (OTHER, 1)])

    with pytest.raises(CardSplitError):
        await game_card(card, cross(binding), "Chrono Cross (USA).cue")


@pytest.mark.asyncio
async def test_a_ps2_card_gives_the_games_folders_alone(binding):
    ace = binding.SigilResult.persisted("ps2", "SLUS-20152", "BASLUS-20152", 0)
    norrath = binding.SigilResult.persisted("ps2", "SLUS-20565", "BASLUS-20565", 0)
    card = ps2_card(
        binding,
        [
            (ace, ps2_folder_unit("BASLUS-20152AC04", b"\x11" * 3000)),
            (norrath, ps2_folder_unit("BASLUS-20565", b"\x22" * 2000)),
        ],
    )

    found = await game_card(
        card, SigilGame(result=ace, game_ids=("SLUS-20152",)), "Ace Combat 04.iso"
    )

    assert found.contents == CardContents.OTHER_GAMES_TOO
    assert found.unit is not None
    assert card_entries(binding, found.unit) == {"BASLUS-20152AC04": "SLUS-20152"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("region", "code", "title_id"),
    [("USA", "GUGE", "47554745"), ("EUR", "GUGP", "47554750")],
)
async def test_a_gamecube_card_gives_the_games_save_file(
    binding, region: str, code: str, title_id: str
):
    nfsu2 = binding.SigilResult.persisted("gamecube", title_id, code, 0)
    sunshine = binding.SigilResult.persisted(
        "gamecube", "474D53" + title_id[-2:], "GMS" + code[-1], 0
    )
    card = gamecube_card(
        binding,
        [
            (nfsu2, gci(code, "69", "NFSU2", 2, 0x11)),
            (sunshine, gci("GMS" + code[-1], "01", "super_mario_sunshine", 1, 0x22)),
        ],
        region,
    )

    found = await game_card(
        card, SigilGame(result=nfsu2, game_ids=(title_id,)), "NFSU2.iso"
    )

    assert found.contents == CardContents.OTHER_GAMES_TOO
    assert found.shape == "single"
    assert found.artifact.endswith(".gci")
    assert found.unit is not None
    assert found.unit[:4] == code.encode()
    assert found.unit[64:] == bytes([0x11]) * 2 * GAMECUBE_BLOCK
