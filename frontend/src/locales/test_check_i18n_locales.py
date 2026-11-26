import unittest

from check_i18n_locales import mixed_script_words, placeholder_mismatches


class PlaceholderMismatchesTest(unittest.TestCase):
    def test_matching_placeholders_pass(self) -> None:
        en = {"greeting": "Hello {name}, {count} new"}
        lang = {"greeting": "{count} nuevos, hola { name }"}
        self.assertEqual(placeholder_mismatches(en, lang), [])

    def test_reports_missing_and_extra(self) -> None:
        en = {"failed": "Unable to edit user: {detail}"}
        lang = {"failed": "No se pudo editar el usuario: {error}"}
        self.assertEqual(
            placeholder_mismatches(en, lang), [("failed", ["detail"], ["error"])]
        )

    def test_checks_nested_keys(self) -> None:
        en = {"user": {"created": "User {username} created"}}
        lang = {"user": {"created": "Usuario creado"}}
        self.assertEqual(
            placeholder_mismatches(en, lang), [("user.created", ["username"], [])]
        )

    def test_skips_keys_missing_from_translation(self) -> None:
        self.assertEqual(placeholder_mismatches({"a": "{x}"}, {}), [])


class MixedScriptWordsTest(unittest.TestCase):
    def test_reports_latin_glued_to_cyrillic(self) -> None:
        lang = {"rom": {"hashes": "ХешісCity in Germany"}, "a": "зупиненоName"}
        self.assertEqual(
            mixed_script_words(lang),
            [("rom.hashes", "ХешісCity"), ("a", "зупиненоName")],
        )

    def test_reports_cyrillic_glued_to_latin(self) -> None:
        self.assertEqual(mixed_script_words({"a": "RomМ"}), [("a", "RomМ")])

    def test_separated_words_pass(self) -> None:
        lang = {
            "a": "Відкрити в RomM",
            "b": "QR-код, PICO-8 і 3D-коробка",
            "c": "Ігор: {count}",
        }
        self.assertEqual(mixed_script_words(lang), [])

    def test_placeholders_do_not_join_words(self) -> None:
        self.assertEqual(mixed_script_words({"a": "Гра{name}Ok"}), [])


if __name__ == "__main__":
    unittest.main()
