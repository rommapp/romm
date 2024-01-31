import pytest
from urllib.parse import urlparse

from handler.igdb_handler import IGDBHandler

igdb_handler = IGDBHandler()


@pytest.mark.vcr()
def test_get_platform():
    platform = igdb_handler.get_platform("n64")
    assert platform["igdb_id"] == 4
    assert platform["name"] == "Nintendo 64"

    platform = igdb_handler.get_platform("not-real")
    assert platform == {"igdb_id": None, "name": "Not Real"}


@pytest.mark.vcr()
async def test_get_rom():
    rom = await igdb_handler.get_rom("Paper Mario (USA).n64", 4)
    assert rom["igdb_id"] == 3340
    assert rom["slug"] == "paper-mario"
    assert rom["name"] == "Paper Mario"
    assert rom["summary"]
    assert urlparse(rom["url_cover"]).hostname == "images.igdb.com"
    assert urlparse(rom["url_screenshots"][0]).hostname == "images.igdb.com"

    rom = await igdb_handler.get_rom("Not a real game title", 4)
    assert not rom["igdb_id"]
    assert rom["slug"] == ""
    assert rom["name"] == "Not a real game title"
    assert not rom["summary"]
    assert rom["url_cover"] == ""
    assert not rom["url_screenshots"]


@pytest.mark.vcr()
async def test_get_ps2_opl_rom():
    rom = await igdb_handler.get_rom("WWE Smack.iso", 8)
    assert not rom["igdb_id"]
    assert rom["slug"] == ""
    assert rom["name"] == "WWE Smack"
    assert not rom["summary"]
    assert rom["url_cover"] == ""
    assert not rom["url_screenshots"]

    rom = await igdb_handler.get_rom("SLUS_210.60.iso", 8)
    assert rom["igdb_id"] == 80852
    assert rom["slug"] == "wwe-smackdown-vs-raw"
    assert rom["name"] == "WWE Smackdown! vs. Raw"
    assert rom["summary"]
    assert urlparse(rom["url_cover"]).hostname == "images.igdb.com"
    assert urlparse(rom["url_screenshots"][0]).hostname == "images.igdb.com"

@pytest.mark.vcr()
def test_get_rom_by_id():
    rom = igdb_handler.get_rom_by_id(3340)
    assert rom["igdb_id"] == 3340
    assert rom["slug"] == "paper-mario"
    assert rom["name"] == "Paper Mario"
    assert rom["summary"]
    assert urlparse(rom["url_cover"]).hostname == "images.igdb.com"
    assert urlparse(rom["url_screenshots"][0]).hostname == "images.igdb.com"

    rom = igdb_handler.get_rom_by_id(-1)
    assert rom["igdb_id"] == -1
    assert not rom["name"]


@pytest.mark.vcr()
def test_get_matched_roms_by_id():
    roms = igdb_handler.get_matched_roms_by_id(3340)
    assert len(roms) == 1

    assert roms[0]["igdb_id"] == 3340
    assert roms[0]["slug"] == "paper-mario"
    assert "t_cover_big" in roms[0]["url_cover"]


@pytest.mark.vcr()
def test_get_matched_roms_by_name():
    roms = igdb_handler.get_matched_roms_by_name("Mario", 4)
    assert len(roms) == 10

    assert roms[0]["igdb_id"] == 132642
    assert roms[0]["slug"] == "super-mario-64-shindou-pak-taiou-version"
    assert roms[0]["name"] == "Super Mario 64: Shindou Pak Taiou Version"

    assert roms[1]["igdb_id"] == 3475
    assert roms[1]["slug"] == "dr-mario-64"
    assert roms[1]["name"] == "Dr. Mario 64"

    roms = igdb_handler.get_matched_roms_by_name("Notarealgametitle", 4)
    assert roms == []
