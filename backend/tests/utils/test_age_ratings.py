import pytest

from utils.age_ratings import compute_min_age, rating_min_age


@pytest.mark.parametrize(
    ("board", "rating", "age"),
    [
        # IGDB's spellings.
        ("ESRB", "EC", 3),
        ("ESRB", "E", 6),
        ("ESRB", "E10+", 10),
        ("ESRB", "T", 13),
        ("ESRB", "M", 17),
        ("ESRB", "AO", 18),
        ("PEGI", "16", 16),
        ("CERO", "A", 0),
        ("CERO", "D", 17),
        ("USK", "12", 12),
        ("GRAC", "ALL", 0),
        ("GRAC", "19+", 19),
        ("CLASS_IND", "L", 0),
        ("CLASS_IND", "14", 14),
        ("ACB", "MA 15+", 15),
        ("ACB", "R 18+", 18),
        # The manual editor's spellings.
        ("ESRB", "E10", 10),
        ("GRAC", "All", 0),
        ("CLASS_IND (Brazil)", "10", 10),
        ("ACB (Australia)", "MA15", 15),
        # ScreenScraper's boards.
        ("SS", "6", 6),
        ("ESRB", "KA", 6),
        ("DJCTQ", "L", 0),
        ("OFLC", "G", 0),
        ("ELSPA", "3", 3),
        ("JV", "+3 ans", 3),
    ],
)
def test_known_ratings_map_to_their_minimum_age(board: str, rating: str, age: int):
    assert rating_min_age(board, rating) == age


@pytest.mark.parametrize(
    ("board", "rating"),
    [
        ("ESRB", "RP"),
        ("GRAC", "TESTING"),
        ("SS", ""),
        ("Tectoy", "TI"),
        ("Unknown", "M"),
    ],
)
def test_pending_or_unknown_ratings_set_no_age(board: str, rating: str):
    assert rating_min_age(board, rating) is None


def test_the_strictest_provider_rating_wins():
    metadata = {
        "igdb_metadata": {"age_ratings": [{"category": "ESRB", "rating": "T"}]},
        "ss_metadata": {"age_ratings": [{"category": "PEGI", "rating": "16"}]},
        "launchbox_metadata": {"esrb": "E"},
    }

    assert compute_min_age(metadata) == 16


def test_a_manual_rating_replaces_the_providers():
    metadata = {
        "manual_metadata": {"age_ratings": ["ESRB:E10"]},
        "igdb_metadata": {"age_ratings": [{"category": "ESRB", "rating": "M"}]},
        "steam_metadata": {"required_age": 18},
    }

    assert compute_min_age(metadata) == 10


def test_steam_counts_only_a_real_age_gate():
    assert compute_min_age({"steam_metadata": {"required_age": 17}}) == 17
    assert compute_min_age({"steam_metadata": {"required_age": 0}}) is None


def test_unrated_and_malformed_metadata_set_no_age():
    assert compute_min_age({}) is None
    assert compute_min_age({"igdb_metadata": None, "ss_metadata": "oops"}) is None
    assert (
        compute_min_age({"manual_metadata": {"age_ratings": ["no colon", 7]}}) is None
    )
