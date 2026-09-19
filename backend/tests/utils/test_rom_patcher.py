import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from anyio import Path as AnyioPath

from utils.rom_patcher import (
    SUPPORTED_PATCH_EXTENSIONS,
    PatcherInputError,
    apply_patch,
)
from utils.rom_patcher import patcher as rom_patcher


def _write_zip(
    path: Path,
    members: dict[str, bytes],
    *,
    comment: bytes = b"",
) -> None:
    rom_patcher.ensure_zipfile_writable()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.comment = comment
        for name, content in members.items():
            archive.writestr(name, content)


def _fake_patcher(
    expected_source: bytes,
    patched_content: bytes,
    *,
    validated: bool = True,
) -> Callable[[Path, Path, Path], Awaitable[bool]]:
    async def patch(rom_path: Path, _patch_path: Path, output_path: Path) -> bool:
        assert await AnyioPath(rom_path).read_bytes() == expected_source
        await AnyioPath(output_path).write_bytes(patched_content)
        return validated

    return patch


def test_supported_patch_extensions_include_xdelta():
    assert ".xdelta" in SUPPORTED_PATCH_EXTENSIONS


@pytest.mark.asyncio
async def test_apply_patch_keeps_raw_rom_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.sfc"
    patch = tmp_path / "translation.bps"
    output = tmp_path / "patched.sfc"
    source.write_bytes(b"source")
    patch.write_bytes(b"patch")
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"source", b"patched", validated=False),
    )

    validated = await apply_patch(source, patch, output)

    assert validated is False
    assert output.read_bytes() == b"patched"


@pytest.mark.asyncio
async def test_apply_patch_rebuilds_single_member_snes_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    patch = tmp_path / "translation.bps"
    output = tmp_path / "patched.zip"
    _write_zip(source, {"Super Metroid.sfc": b"source"}, comment=b"archive comment")
    patch.write_bytes(b"patch")
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"source", b"patched"),
    )

    validated = await apply_patch(source, patch, output)

    assert validated is True
    assert source.read_bytes() != output.read_bytes()
    with zipfile.ZipFile(source) as archive:
        assert archive.read("Super Metroid.sfc") == b"source"
    with zipfile.ZipFile(output) as archive:
        assert archive.comment == b"archive comment"
        assert archive.namelist() == ["Super Metroid.sfc"]
        assert archive.read("Super Metroid.sfc") == b"patched"
        member = archive.getinfo("Super Metroid.sfc")
        assert member.compress_type == zipfile.ZIP_DEFLATED
        # A small member must stay readable by minimal unzip implementations.
        assert member.extract_version < zipfile.ZIP64_VERSION
        assert archive.testzip() is None
    # The full-size intermediates are dropped once the archive is rebuilt.
    assert not (tmp_path / "source_rom").exists()
    assert not (tmp_path / "patched_rom").exists()


@pytest.mark.asyncio
async def test_apply_patch_uses_archive_fallback_for_unsupported_zip_method(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    output = tmp_path / "patched.zip"
    member_name = "game.sfc"
    _write_zip(source, {member_name: b"source"})
    data = bytearray(source.read_bytes())
    encoded_name = member_name.encode()
    local_header = data.index(encoded_name, data.index(b"PK\x03\x04")) - 30
    central_header = data.index(encoded_name, data.index(b"PK\x01\x02")) - 46
    data[local_header + 8 : local_header + 10] = (0xFFFF).to_bytes(2, "little")
    data[central_header + 10 : central_header + 12] = (0xFFFF).to_bytes(2, "little")
    source.write_bytes(data)
    archive_reader = MagicMock(
        return_value=iter([(member_name, len(b"source"), iter([b"source"]))])
    )
    monkeypatch.setattr(rom_patcher, "read_zip_archive_files", archive_reader)
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"source", b"patched"),
    )

    await apply_patch(source, tmp_path / "patch.bps", output)

    archive_reader.assert_called_once_with(source, [], [])
    with zipfile.ZipFile(output) as archive:
        assert archive.read(member_name) == b"patched"


@pytest.mark.asyncio
async def test_apply_patch_replaces_selected_member_and_preserves_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    patch = tmp_path / "translation.ips"
    output = tmp_path / "patched.zip"
    _write_zip(
        source,
        {
            "docs/readme.txt": b"instructions",
            "roms/game.smc": b"source",
        },
    )
    patch.write_bytes(b"patch")
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"source", b"patched"),
    )

    await apply_patch(source, patch, output, "roms/game.smc")

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["docs/readme.txt", "roms/game.smc"]
        assert archive.read("docs/readme.txt") == b"instructions"
        assert archive.read("roms/game.smc") == b"patched"


@pytest.mark.asyncio
async def test_apply_patch_requires_member_for_multi_file_zip(tmp_path: Path):
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"source", "readme.txt": b"readme"})

    with pytest.raises(PatcherInputError, match="Select which file"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")


@pytest.mark.asyncio
async def test_apply_patch_rejects_missing_archive_member(tmp_path: Path):
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"source", "readme.txt": b"readme"})

    with pytest.raises(PatcherInputError, match="not found uniquely"):
        await apply_patch(
            source,
            tmp_path / "patch.bps",
            tmp_path / "patched.zip",
            "missing.sfc",
        )


@pytest.mark.asyncio
async def test_apply_patch_does_not_extract_member_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    output = tmp_path / "patched.zip"
    _write_zip(source, {"../../game.sfc": b"source", "readme.txt": b"readme"})
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"source", b"patched"),
    )

    await apply_patch(source, tmp_path / "patch.bps", output, "../../game.sfc")

    assert not (tmp_path.parent / "game.sfc").exists()
    with zipfile.ZipFile(output) as archive:
        assert archive.read("../../game.sfc") == b"patched"


@pytest.mark.asyncio
async def test_apply_patch_rejects_corrupt_zip(tmp_path: Path):
    source = tmp_path / "game.zip"
    source.write_bytes(b"not a zip")

    with pytest.raises(PatcherInputError, match="could not be read"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")


@pytest.mark.asyncio
async def test_apply_patch_reports_zip_input_oserror_as_input_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    source.write_bytes(b"input")

    def raise_input_error(*_args: object, **_kwargs: object) -> None:
        raise OSError("input read failed")

    monkeypatch.setattr(rom_patcher.zipfile, "ZipFile", raise_input_error)

    with pytest.raises(PatcherInputError, match="could not be read"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")


@pytest.mark.asyncio
async def test_apply_patch_does_not_report_extraction_output_oserror_as_input_error(
    tmp_path: Path,
):
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"source"})
    output = tmp_path / "missing" / "patched.zip"

    with pytest.raises(OSError):
        await apply_patch(source, tmp_path / "patch.bps", output)


@pytest.mark.asyncio
async def test_apply_patch_does_not_report_rebuild_output_oserror_as_input_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    output = tmp_path / "patched.zip"
    _write_zip(source, {"game.sfc": b"source"})
    output.mkdir()
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"source", b"patched"),
    )

    with pytest.raises(OSError):
        await apply_patch(source, tmp_path / "patch.bps", output)


@pytest.mark.asyncio
async def test_apply_patch_rejects_oversized_uncompressed_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"large"})
    monkeypatch.setattr(rom_patcher, "ROM_PATCHER_MAX_FILE_SIZE_BYTES", 4)

    with pytest.raises(PatcherInputError, match="uncompressed ROM is too large"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")


@pytest.mark.asyncio
async def test_apply_patch_stops_a_member_that_outgrows_its_declared_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # An archive zipfile cannot decode is read through 7zz, which decompresses
    # it itself, so the entry's declared size is only the uploader's word.
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"rom"})
    monkeypatch.setattr(rom_patcher, "ROM_PATCHER_MAX_FILE_SIZE_BYTES", 8)

    pulled = 0

    def _lying_reader(*_args, **_kwargs):
        def _chunks():
            nonlocal pulled
            for _ in range(100):
                pulled += 1
                yield b"X" * 16

        yield "game.sfc", 3, _chunks()

    monkeypatch.setattr(rom_patcher, "read_zip_archive_files", _lying_reader)

    with pytest.raises(PatcherInputError, match="uncompressed ROM is too large"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")

    # Bailed on the first chunk past the budget rather than writing all 1600 bytes.
    assert pulled == 1


@pytest.mark.asyncio
async def test_apply_patch_rejects_oversized_patched_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"rom"})
    monkeypatch.setattr(rom_patcher, "ROM_PATCHER_MAX_FILE_SIZE_BYTES", 4)
    monkeypatch.setattr(
        rom_patcher,
        "_apply_binary_patch",
        _fake_patcher(b"rom", b"large"),
    )

    with pytest.raises(PatcherInputError, match="patched ROM is too large"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")


@pytest.mark.asyncio
async def test_apply_patch_rejects_encrypted_zip(tmp_path: Path):
    source = tmp_path / "game.zip"
    _write_zip(source, {"game.sfc": b"rom"})
    data = bytearray(source.read_bytes())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        index = data.index(signature)
        flags = int.from_bytes(
            data[index + flag_offset : index + flag_offset + 2], "little"
        )
        data[index + flag_offset : index + flag_offset + 2] = (flags | 1).to_bytes(
            2, "little"
        )
    source.write_bytes(data)

    with pytest.raises(PatcherInputError, match="Encrypted"):
        await apply_patch(source, tmp_path / "patch.bps", tmp_path / "patched.zip")


@pytest.mark.asyncio
async def test_apply_patch_rejects_unsupported_archive_format(tmp_path: Path):
    with pytest.raises(PatcherInputError, match="not supported"):
        await apply_patch(
            tmp_path / "game.7z",
            tmp_path / "patch.bps",
            tmp_path / "patched.7z",
        )
