"""Tests for the MAME index parser and the MAME metadata source."""

import io
import json
from typing import Any
from unittest.mock import AsyncMock, patch


from handler.metadata.mame_handler import (
    MameHandler,
    set_name_of,
    set_type_of,
    year_epoch,
)
from handler.metadata.mame_index import iter_listxml

LISTXML = b"""<?xml version="1.0"?>
<mame build="0.289 (mame0289)">
  <machine name="sfiii" sourcefile="capcom/cps3.cpp">
    <description>Street Fighter III: New Generation (Europe 970204)</description>
    <year>1997</year>
    <manufacturer>Capcom</manufacturer>
    <rom name="sfiii_euro.29f400.u2" size="524288" crc="27699ddc"/>
    <input players="2" coins="2"/>
    <driver status="good" emulation="good"/>
  </machine>
  <machine name="sfiiia" sourcefile="capcom/cps3.cpp" cloneof="sfiii" romof="sfiii">
    <description>Street Fighter III: New Generation (Asia 970204)</description>
    <year>1997</year>
    <manufacturer>Capcom</manufacturer>
    <driver status="imperfect"/>
  </machine>
  <machine name="neogeo" sourcefile="neogeo/neogeo.cpp" isbios="yes">
    <description>Neo-Geo MV-6F</description>
    <year>1990</year>
    <manufacturer>SNK</manufacturer>
  </machine>
  <machine name="z80" isdevice="yes" runnable="no">
    <description>Zilog Z80</description>
  </machine>
  <machine name="pinball" sourcefile="misc/pin.cpp" ismechanical="yes">
    <description>Some Pinball</description>
    <year>19??</year>
  </machine>
</mame>
"""


def _machines() -> dict[str, Any]:
    return {m["name"]: (build, m) for build, m in iter_listxml(io.BytesIO(LISTXML))}


def test_iter_listxml_reads_every_set_and_build():
    machines = _machines()
    assert set(machines) == {"sfiii", "sfiiia", "neogeo", "z80", "pinball"}
    build, sfiii = machines["sfiii"]
    assert build == "0.289 (mame0289)"
    assert sfiii["description"] == "Street Fighter III: New Generation (Europe 970204)"
    assert sfiii["sourcefile"] == "capcom/cps3.cpp"
    assert sfiii["status"] == "good"
    assert sfiii["players"] == 2
    assert sfiii["cloneof"] is None


def test_iter_listxml_flags():
    machines = _machines()
    assert machines["sfiiia"][1]["cloneof"] == "sfiii"
    assert machines["neogeo"][1]["is_bios"] is True
    assert machines["z80"][1]["is_device"] is True
    assert machines["z80"][1]["runnable"] is False
    assert machines["pinball"][1]["is_mechanical"] is True


def test_set_types():
    machines = _machines()
    assert set_type_of(machines["sfiii"][1]) == "parent"
    assert set_type_of(machines["sfiiia"][1]) == "clone"
    assert set_type_of(machines["neogeo"][1]) == "bios"
    assert set_type_of(machines["z80"][1]) == "device"


def test_set_name_and_year():
    assert set_name_of("SFIIIA.zip") == "sfiiia"
    assert set_name_of("sfiii") == "sfiii"
    assert year_epoch("1997") == 852076800
    assert year_epoch("19??") is None
    assert year_epoch(None) is None


async def test_match_machine_from_loaded_index():
    machines = _machines()
    with (
        patch(
            "handler.metadata.mame_handler.get_machine",
            AsyncMock(return_value=machines["sfiiia"][1]),
        ),
        patch(
            "handler.metadata.mame_handler.get_index_info",
            AsyncMock(return_value={"build": "0.289 (mame0289)"}),
        ),
        patch(
            "handler.metadata.mame_handler.async_cache.hget",
            AsyncMock(return_value=json.dumps({"genre": "Fighter"})),
        ),
    ):
        rom = await MameHandler().match_machine("sfiiia.zip")

    assert rom["mame_id"] == "sfiii"
    assert rom["name"] == "Street Fighter III: New Generation (Asia 970204)"
    metadata = rom["mame_metadata"]
    assert metadata["set_type"] == "clone"
    assert metadata["status"] == "imperfect"
    assert metadata["sourcefile"] == "capcom/cps3.cpp"
    assert metadata["is_mechanical"] is False
    assert metadata["companies"] == ["Capcom"]
    assert metadata["genres"] == ["Fighter"]
    assert metadata["first_release_date"] == 852076800
    assert metadata["mame_build"] == "0.289 (mame0289)"


async def test_match_machine_falls_back_to_bundled_index():
    fixture = {"description": "Street Fighter II", "cloneof": None, "year": "1991"}
    with (
        patch(
            "handler.metadata.mame_handler.get_machine", AsyncMock(return_value=None)
        ),
        patch(
            "handler.metadata.mame_handler.async_cache.hget",
            AsyncMock(return_value=json.dumps(fixture)),
        ),
    ):
        rom = await MameHandler().match_machine("sf2.zip")

    assert rom["mame_id"] == "sf2"
    assert rom["name"] == "Street Fighter II"
    assert rom["mame_metadata"]["set_type"] == "parent"
    assert "is_mechanical" not in rom["mame_metadata"]
    assert "sourcefile" not in rom["mame_metadata"]


async def test_match_machine_misses():
    with (
        patch(
            "handler.metadata.mame_handler.get_machine", AsyncMock(return_value=None)
        ),
        patch(
            "handler.metadata.mame_handler.async_cache.hget",
            AsyncMock(return_value=None),
        ),
    ):
        assert (await MameHandler().match_machine("nothere.zip"))["mame_id"] is None
