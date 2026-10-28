import unittest

from check_i18n_locales import placeholder_mismatches


class PlaceholderMismatchesTest(unittest.TestCase):
    def test_matching_placeholders_pass(self):
        en = {"greeting": "Hello {name}, {count} new"}
        lang = {"greeting": "{count} nuevos, hola { name }"}
        self.assertEqual(placeholder_mismatches(en, lang), [])

    def test_reports_missing_and_extra(self):
        en = {"failed": "Unable to edit user: {detail}"}
        lang = {"failed": "No se pudo editar el usuario: {error}"}
        self.assertEqual(
            placeholder_mismatches(en, lang), [("failed", ["detail"], ["error"])]
        )

    def test_checks_nested_keys(self):
        en = {"user": {"created": "User {username} created"}}
        lang = {"user": {"created": "Usuario creado"}}
        self.assertEqual(
            placeholder_mismatches(en, lang), [("user.created", ["username"], [])]
        )

    def test_skips_keys_missing_from_translation(self):
        self.assertEqual(placeholder_mismatches({"a": "{x}"}, {}), [])


if __name__ == "__main__":
    unittest.main()
