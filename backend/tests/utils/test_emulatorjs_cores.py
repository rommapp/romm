from utils.emulatorjs_cores import EJS_CORES_BY_PLATFORM
from utils.platform_slugs import UniversalPlatformSlug as UPS


def test_each_arcade_family_gets_the_cores_that_run_its_sets():
    assert EJS_CORES_BY_PLATFORM[UPS.MAME] == ["mame2003_plus", "mame2003"]
    assert EJS_CORES_BY_PLATFORM[UPS.FBNEO] == ["fbneo"]
    assert EJS_CORES_BY_PLATFORM[UPS.FBA] == [
        "fbneo",
        "fbalpha2012_cps1",
        "fbalpha2012_cps2",
    ]
    assert "fbneo" in EJS_CORES_BY_PLATFORM[UPS.ARCADE]


def test_a_board_emulatorjs_cannot_run_has_no_core():
    assert UPS.NAOMI not in EJS_CORES_BY_PLATFORM
    assert UPS.MAME_ADVMAME not in EJS_CORES_BY_PLATFORM
