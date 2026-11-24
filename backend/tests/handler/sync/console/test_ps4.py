import pytest
from tests.handler.sync.console.fakes import PS4_SAVEDATA, FakeConsole, build_sfo

from handler.sync.console.ps4 import PS4, discover_title_ids, is_save


class TestIsSave:
    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            ({"sdimg_SAVEDATA00", "SAVEDATA00.bin"}, True),
            (
                {
                    "sdimg_PROFILE",
                    "PROFILE.bin",
                    "sdimg_sce_bu_PROFILE",
                    "sce_bu_PROFILE.bin",
                },
                True,
            ),
            ({"sdimg_SAVEDATA00"}, False),
            ({"SAVEDATA00.bin"}, False),
            ({"sdimg_A", "A.bin", "notes.txt"}, False),
            (set(), False),
        ],
    )
    def test_needs_each_image_with_its_key(self, names: set[str], expected: bool):
        assert is_save(names) is expected


class TestDiscoverTitleIds:
    async def test_finds_games_on_internal_and_extended_storage(self):
        console = FakeConsole(PS4_SAVEDATA)
        console.add_dir("/user/app/CUSA00960")
        console.add_dir("/user/app/NPXS39041")
        console.add_dir("/user/app/notagame")
        console.add_dir("/mnt/ext0/user/app/CUSA18886")

        assert await discover_title_ids(console, "device-1") == {
            "CUSA00960",
            "NPXS39041",
            "CUSA18886",
        }


class TestPS4Profile:
    def test_paths(self):
        assert PS4.savedata_path("1cabafc9") == "/user/home/1cabafc9/savedata"
        assert PS4.default_ftp_port == 2121
        assert PS4.save_folder_pattern.match("CUSA18886")
        assert not PS4.save_folder_pattern.match("sce_backup")

    async def test_save_title_comes_from_the_installed_game(self):
        console = FakeConsole(PS4_SAVEDATA)
        console.add_file(
            "/system_data/priv/appmeta/CUSA18886/param.sfo",
            build_sfo(TITLE="Sackboy™: A Big Adventure"),
        )
        folder = f"{PS4_SAVEDATA}/CUSA18886"

        title = await PS4.save_title(console, folder, [])

        assert title == "Sackboy™: A Big Adventure"

    async def test_no_save_title_without_the_game_metadata(self):
        console = FakeConsole(PS4_SAVEDATA)

        assert await PS4.save_title(console, f"{PS4_SAVEDATA}/CUSA00001", []) is None
