from tests.handler.sync.console.fakes import FakeConsole, build_ps3_iso, build_sfo

from handler.sync.console.ps3 import PS3, discover_title_ids


class TestDiscoverTitleIds:
    async def test_finds_installed_iso_and_folder_games(self):
        console = FakeConsole()
        console.add_dir("/dev_hdd0/game/BLES00801")
        console.add_dir("/dev_hdd0/game/PKGLAUNCH")
        console.add_file(
            "/dev_hdd0/PS3ISO/FALLOUT 3.ISO",
            build_ps3_iso(build_sfo(TITLE_ID="BLES00333", TITLE="FALLOUT 3")),
        )
        console.add_file("/dev_hdd0/PS3ISO/FALLOUT 3.png", b"cover")
        console.add_file("/dev_usb000/PS3ISO/Jak [BCUS98281].iso", b"never read")
        console.add_file(
            "/dev_hdd0/GAMES/MotorStorm/PS3_GAME/PARAM.SFO",
            build_sfo(TITLE_ID="BCES00006"),
        )

        title_ids = await discover_title_ids(console, "device-1")

        assert title_ids == {"BLES00801", "BLES00333", "BCUS98281", "BCES00006"}
        assert "/dev_usb000/PS3ISO/Jak [BCUS98281].iso" not in console.reads

    async def test_reads_each_image_once(self):
        console = FakeConsole()
        console.add_file(
            "/dev_hdd0/PS3ISO/Game.iso",
            build_ps3_iso(build_sfo(TITLE_ID="BLES00333")),
        )
        await discover_title_ids(console, "device-1")
        console.reads.clear()

        assert await discover_title_ids(console, "device-1") == {"BLES00333"}
        assert console.reads == []

    async def test_skips_an_image_it_cannot_read(self):
        console = FakeConsole()
        console.add_file("/dev_hdd0/PS3ISO/Broken.iso", b"not an image")

        assert await discover_title_ids(console, "device-1") == set()


class TestPS3Profile:
    def test_a_save_has_a_param_sfo(self):
        assert PS3.is_save({"PARAM.SFO", "SAVEDATA.000"})
        assert not PS3.is_save({"SAVEDATA.000"})

    async def test_save_title_is_read_from_param_sfo(self):
        console = FakeConsole()
        folder = f"{console.savedata}/BLES01138SAVE"
        console.add_file(f"{folder}/PARAM.SFO", build_sfo(TITLE="Far Cry 3"))

        files = await console.list(folder)

        assert await PS3.save_title(console, folder, files) == "Far Cry 3"
