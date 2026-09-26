import contextlib
import enum
import json
from typing import NotRequired, TypedDict
from unittest.mock import MagicMock

import pytest

from adapters.services import response_validation
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


@pytest.fixture
def lenient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(response_validation, "RAISE_ON_MISMATCH", False)
    monkeypatch.setattr(response_validation, "_reported", set())


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


@pytest.mark.usefixtures("lenient")
def test_mismatch_returns_raw_payload_and_logs_once(monkeypatch: pytest.MonkeyPatch):
    log = MagicMock()
    monkeypatch.setattr(response_validation, "log", log)
    data = [{"id": 1, "kind": 9, "child": {"id": 2}}]

    first = validate_response(list[Parent], data, source="Provider endpoint")
    second = validate_response(list[Parent], data, source="Provider endpoint")

    assert first is data
    assert second is data
    log.warning.assert_called_once()
    message = log.warning.call_args.args[0] % log.warning.call_args.args[1:]
    assert "Provider endpoint" in message
    assert "*.kind" in message


@pytest.mark.usefixtures("lenient")
def test_id_keyed_entries_share_one_warning(monkeypatch: pytest.MonkeyPatch):
    log = MagicMock()
    monkeypatch.setattr(response_validation, "log", log)

    validate_response(dict[str, Child], {"101": {"id": "x"}}, source="test")
    validate_response(dict[str, Child], {"202": {"id": "y"}}, source="test")

    log.warning.assert_called_once()


@pytest.mark.usefixtures("lenient")
def test_known_problems_in_a_new_combination_are_not_logged_again(
    monkeypatch: pytest.MonkeyPatch,
):
    log = MagicMock()
    monkeypatch.setattr(response_validation, "log", log)

    validate_response(list[Child], [{"id": "x"}], source="test")
    validate_response(list[Child], [{"id": None}], source="test")
    validate_response(list[Child], [{"id": "x"}, {"id": None}], source="test")

    assert log.warning.call_count == 2
