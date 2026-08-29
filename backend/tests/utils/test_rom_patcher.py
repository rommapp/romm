from utils.rom_patcher import SUPPORTED_PATCH_EXTENSIONS


def test_supported_patch_extensions_include_xdelta():
    assert ".xdelta" in SUPPORTED_PATCH_EXTENSIONS
