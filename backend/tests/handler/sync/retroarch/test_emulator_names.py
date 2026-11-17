import unittest

from handler.sync.retroarch.emulator_names import (
    retroarch_aliases,
    to_retroarch_dir_name,
    to_romm_emulator,
)


class TestMelonDSDSNames(unittest.TestCase):
    def test_both_ids_use_the_core_folder(self):
        for emulator in ("melondsds", "melonds_ds"):
            with self.subTest(emulator=emulator):
                self.assertEqual(to_retroarch_dir_name(emulator), "melonDS DS")

    def test_uploads_use_the_libretro_id(self):
        self.assertEqual(to_romm_emulator("melonDS DS"), "melondsds")

    def test_all_spellings_share_assets(self):
        aliases = ("melonDS DS", "melonds_ds", "melondsds")
        for emulator in aliases:
            with self.subTest(emulator=emulator):
                self.assertEqual(retroarch_aliases(emulator), aliases)

    def test_original_melonds_remains_separate(self):
        self.assertEqual(to_retroarch_dir_name("melonds"), "melonDS")
        self.assertEqual(to_romm_emulator("melonDS"), "melonds")
        self.assertEqual(retroarch_aliases("melonds"), ("melonDS", "melonds"))
