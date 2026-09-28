import pytest

from utils import switch


class TestIsBaseTitleId:
    @pytest.mark.parametrize(
        "title_id",
        ["0100ABCD12340000", "0100F4700B2E0000", "0100abcd12340000"],
    )
    def test_base_ids_are_recognized(self, title_id: str):
        assert switch.is_base_title_id(title_id)

    @pytest.mark.parametrize(
        "title_id",
        [
            "0100ABCD12340800",  # update: odd program-index nibble
            "0100ABCD12341001",  # DLC: low bits set
            "",
            "000",
            "0100ABCD1234ZZZ0",  # non-hex nibble
        ],
    )
    def test_non_base_ids_are_rejected(self, title_id: str):
        assert not switch.is_base_title_id(title_id)


class TestDeriveBaseTitleId:
    def test_update_resolves_to_its_base(self):
        assert switch.derive_base_title_id("0100ABCD12340800") == "0100ABCD12340000"

    def test_dlc_resolves_to_its_base(self):
        assert switch.derive_base_title_id("0100ABCD12341001") == "0100ABCD12340000"

    def test_a_base_id_is_left_alone(self):
        assert switch.derive_base_title_id("0100ABCD12340000") == "0100ABCD12340000"

    def test_case_of_the_program_index_nibble_is_preserved(self):
        assert switch.derive_base_title_id("0100abcd1234e000") == "0100abcd1234e000"
        assert switch.derive_base_title_id("0100ABCD1234E000") == "0100ABCD1234E000"

    @pytest.mark.parametrize("title_id", ["", "000", "0100ABCD1234ZZZ0"])
    def test_unparseable_ids_yield_nothing(self, title_id: str):
        assert switch.derive_base_title_id(title_id) is None


class TestTitleIdRegexes:
    def test_a_bare_id_matches_the_plain_regex(self):
        assert switch.TITLE_ID_REGEX.fullmatch("0100ABCD12340000")

    @pytest.mark.parametrize(
        "value",
        ["0100ABCD1234000", "0100ABCD123400001", "[0100ABCD12340000]", "xyz"],
    )
    def test_anything_else_does_not(self, value: str):
        assert not switch.TITLE_ID_REGEX.fullmatch(value)

    def test_an_embedded_id_is_found_anywhere_in_a_name(self):
        assert switch.TITLE_ID_BRACKET_REGEX.search("Game [0100ABCD12340000][v0].nsp")

    def test_a_name_without_one_is_not_matched(self):
        assert not switch.TITLE_ID_BRACKET_REGEX.search("Game [USA][v0].nsp")
