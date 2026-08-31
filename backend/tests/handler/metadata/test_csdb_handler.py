from unittest.mock import AsyncMock, patch

import pytest

from handler.metadata.csdb_handler import (
    CsdbHandler,
    csdb_id_from_url,
    extract_csdb_id_from_filename,
    production_from_xml,
)

WORKING_STONE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CSDbData><Release>
<ID>75330</ID>
<Name>Working Stone +2P</Name>
<Type>C64 Crack</Type>
<ReleaseYear>1993</ReleaseYear>
<ScreenShot>https://csdb.dk/gfx/releases/75000/75330.png</ScreenShot>
<ReleasedBy><Group><Name>Fairlight</Name></Group></ReleasedBy>
<Credits><Credit><CreditType>Crack</CreditType>
<Handle><Handle>Bacchus</Handle></Handle></Credit></Credits>
</Release></CSDbData>
"""


def test_extract_csdb_id_from_filename():
    assert extract_csdb_id_from_filename("Working Stone +2P (csdb-75330).zip") == 75330
    assert extract_csdb_id_from_filename("Foo (demozoo-2)(CSDB-9).d64") == 9
    assert extract_csdb_id_from_filename("untagged.zip") is None


def test_csdb_id_from_url():
    assert csdb_id_from_url("https://csdb.dk/release/?id=75330") == 75330
    assert csdb_id_from_url("https://csdb.dk/release/?id=75330&x=1") == 75330
    assert csdb_id_from_url("http://www.csdb.dk/release/75330") == 75330
    assert csdb_id_from_url("https://demozoo.org/productions/1/") is None


def test_production_from_xml_cover():
    rom = production_from_xml(WORKING_STONE_XML)
    assert rom["csdb_id"] == 75330
    assert rom["name"] == "Working Stone +2P"
    assert rom["url_cover"] == "https://csdb.dk/gfx/releases/75000/75330.png"
    assert rom["url_screenshots"] == [rom["url_cover"]]
    assert rom["csdb_metadata"]["groups"] == ["Fairlight"]
    assert "https://csdb.dk/release/?id=75330" in (rom.get("summary") or "")
    assert "Fairlight" in (rom.get("summary") or "")


def test_production_from_xml_empty():
    assert production_from_xml("<CSDbData/>")["csdb_id"] is None
    assert production_from_xml("not xml")["csdb_id"] is None
    assert production_from_xml("<CSDbData><Release>")["csdb_id"] is None


def test_production_from_xml_rejects_non_http_screenshot():
    xml = WORKING_STONE_XML.replace(
        "https://csdb.dk/gfx/releases/75000/75330.png",
        "javascript:alert(1)",
    )
    rom = production_from_xml(xml)
    assert rom["url_cover"] == ""
    assert rom["url_screenshots"] == []


@pytest.mark.asyncio
async def test_get_rom_disabled():
    handler = CsdbHandler()
    with patch.object(CsdbHandler, "is_enabled", return_value=False):
        result = await handler.get_rom("Working Stone +2P (csdb-75330).zip", "c64")
    assert result["csdb_id"] is None


@pytest.mark.asyncio
async def test_get_rom_uses_filename_tag():
    handler = CsdbHandler()
    with (
        patch.object(CsdbHandler, "is_enabled", return_value=True),
        patch.object(handler, "get_rom_by_id", new_callable=AsyncMock) as mock_by_id,
    ):
        mock_by_id.return_value = production_from_xml(WORKING_STONE_XML)
        result = await handler.get_rom("Working Stone +2P (csdb-75330).zip", "c64")
    mock_by_id.assert_awaited_once_with(75330)
    assert result["csdb_id"] == 75330


@pytest.mark.asyncio
async def test_get_rom_no_tag_does_not_search():
    handler = CsdbHandler()
    with (
        patch.object(CsdbHandler, "is_enabled", return_value=True),
        patch.object(handler, "get_rom_by_id", new_callable=AsyncMock) as mock_by_id,
    ):
        result = await handler.get_rom("Working Stone +2P (demozoo-396051).zip", "c64")
    mock_by_id.assert_not_called()
    assert result["csdb_id"] is None


def test_production_from_xml_rejects_entity_declarations():
    """defusedxml refuses entities with a ValueError, not a ParseError."""
    xxe = """<?xml version="1.0"?>
<!DOCTYPE CSDbData [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<CSDbData><Release><ID>1</ID><Name>&xxe;</Name></Release></CSDbData>
"""
    assert production_from_xml(xxe)["csdb_id"] is None


@pytest.mark.asyncio
async def test_request_returns_empty_when_over_the_cap():
    handler = CsdbHandler()
    with patch.object(CsdbHandler, "_fetch_capped", AsyncMock(return_value=None)):
        assert await handler._request("https://csdb.dk/webservice/?id=1") == ""
