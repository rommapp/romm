"""Tests for utils.assets helpers."""

import pytest
from fastapi import HTTPException, status

from models.assets import ASSET_LABEL_MAX_LENGTH, ASSET_LABELS_MAX
from utils.assets import normalize_asset_labels


def test_labels_are_trimmed_and_blanks_dropped():
    assert normalize_asset_labels(["  100% run  ", "", "   ", "seed 42"]) == [
        "100% run",
        "seed 42",
    ]


def test_labels_dedupe_case_insensitively_keeping_the_first_spelling():
    assert normalize_asset_labels(["Run", "run", "RUN", "Seed"]) == ["Run", "Seed"]


def test_label_order_is_preserved():
    assert normalize_asset_labels(["z", "a", "m"]) == ["z", "a", "m"]


def test_an_empty_list_stays_empty():
    assert normalize_asset_labels([]) == []


def test_a_label_of_exactly_the_maximum_length_is_kept():
    label = "y" * ASSET_LABEL_MAX_LENGTH
    assert normalize_asset_labels([label]) == [label]


def test_an_overlong_label_is_rejected():
    with pytest.raises(HTTPException) as exc:
        normalize_asset_labels(["fine", "x" * (ASSET_LABEL_MAX_LENGTH + 1)])

    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_the_maximum_number_of_labels_is_kept():
    labels = [f"label {i}" for i in range(ASSET_LABELS_MAX)]
    assert normalize_asset_labels(labels) == labels


def test_too_many_labels_are_rejected():
    with pytest.raises(HTTPException) as exc:
        normalize_asset_labels([f"label {i}" for i in range(ASSET_LABELS_MAX + 1)])

    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_duplicates_beyond_the_cap_collapse_instead_of_being_rejected():
    """The cap counts what is stored, so repeats of one label are not a breach."""
    assert normalize_asset_labels(["same"] * (ASSET_LABELS_MAX + 10)) == ["same"]
