import contextlib
import enum
import json
from typing import NotRequired, TypedDict
from unittest.mock import MagicMock

import pytest

from adapters.services.response_validation import (
    ResponseMismatchError,
    validate_response,
)


class Kind(enum.IntEnum):
    MAIN = 0
    DLC = 1


class Child(TypedDict):
    id: int


class Parent(TypedDict):
    id: int
    kind: Kind
    child: Child
    note: NotRequired[str]
    score: NotRequired[float]


def test_matching_payload_comes_back_as_sent():
    data = {
        "id": 1,
        "kind": 1,
        "child": {"id": 2, "extra": "kept"},
        "score": 80,
        "other": [1],
    }

    assert validate_response(Parent, data, source="test") is data


def test_list_payload_is_validated_per_item():
    data = [{"id": 1}, {"id": 2}]

    assert validate_response(list[Child], data, source="test") == data


@pytest.mark.parametrize("empty", [{}, []])
def test_empty_error_payload_skips_validation(empty: object):
    assert validate_response(Parent, empty, source="test") is empty


@pytest.mark.parametrize("falsy", [None, False, 0, ""])
def test_other_falsy_payloads_are_validated(falsy: object):
    with pytest.raises(ResponseMismatchError):
        validate_response(Parent, falsy, source="test")


def test_mismatch_raises_when_strict():
    with pytest.raises(ResponseMismatchError, match="id"):
        validate_response(Parent, {"id": "x"}, source="test")


def test_mismatch_is_not_swallowed_by_a_broad_except():
    with pytest.raises(ResponseMismatchError), contextlib.suppress(Exception):
        validate_response(Parent, {"id": "x"}, source="test")


def test_nan_is_not_a_coercion():
    data = json.loads('{"id": 1, "kind": 0, "child": {"id": 2}, "score": NaN}')

    assert validate_response(Parent, data, source="test") is data


def test_value_that_fits_only_after_coercion_is_a_mismatch():
    data = {"id": "1", "kind": 0, "child": {"id": 2}}

    with pytest.raises(ResponseMismatchError, match="id: matches only after coercion"):
        validate_response(Parent, data, source="test")


def test_mismatch_returns_raw_payload_and_logs_once(lenient: MagicMock):
    data = [{"id": 1, "kind": 9, "child": {"id": 2}}]

    first = validate_response(list[Parent], data, source="Provider endpoint")
    second = validate_response(list[Parent], data, source="Provider endpoint")

    assert first is data
    assert second is data
    lenient.warning.assert_called_once()
    message = lenient.warning.call_args.args[0] % lenient.warning.call_args.args[1:]
    assert "Provider endpoint" in message
    assert "*.kind" in message


def test_id_keyed_entries_share_one_warning(lenient: MagicMock):
    validate_response(dict[str, Child], {"101": {"id": "x"}}, source="test")
    validate_response(dict[str, Child], {"202": {"id": "y"}}, source="test")

    lenient.warning.assert_called_once()


def test_known_problems_in_a_new_combination_are_not_logged_again(
    lenient: MagicMock,
):
    validate_response(list[Child], [{"id": "x"}], source="test")
    validate_response(list[Child], [{"id": None}], source="test")
    validate_response(list[Child], [{"id": "x"}, {"id": None}], source="test")

    assert lenient.warning.call_count == 2


def test_problems_beyond_a_warning_surface_in_the_next_one(lenient: MagicMock):
    data = {f"k{i}": "x" for i in range(7)}

    validate_response(dict[str, int], data, source="test")
    validate_response(dict[str, int], data, source="test")
    validate_response(dict[str, int], data, source="test")

    assert lenient.warning.call_count == 2
    second = lenient.warning.call_args_list[1].args
    assert second[4].count(":") == 2
