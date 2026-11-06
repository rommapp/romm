from utils.sibling_groups import sibling_groups


def test_roms_sharing_no_key_are_left_out():
    assert sibling_groups([(1, "a"), (2, "b")]) == {}


def test_a_shared_key_groups_under_the_lowest_id():
    assert sibling_groups([(7, "a"), (3, "a")]) == {3: 3, 7: 3}


def test_a_chain_of_different_keys_is_one_group():
    """1 and 3 share nothing, but each shares a key with 2."""
    rows = [(1, "igdb"), (2, "igdb"), (2, "ss"), (3, "ss")]

    assert sibling_groups(rows) == {1: 1, 2: 1, 3: 1}


def test_merging_two_groups_keeps_the_lower_root():
    rows = [(5, "a"), (6, "a"), (2, "b"), (9, "b"), (9, "c"), (6, "c")]

    assert set(sibling_groups(rows).values()) == {2}


def test_separate_groups_stay_separate():
    rows = [(1, "a"), (2, "a"), (3, "b"), (4, "b")]

    assert sibling_groups(rows) == {1: 1, 2: 1, 3: 3, 4: 3}
