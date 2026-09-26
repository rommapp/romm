import enum
from typing import NotRequired, TypedDict
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from adapters.services import response_validation
from adapters.services.response_validation import validate_response


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


@pytest.fixture
def lenient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(response_validation, "RAISE_ON_MISMATCH", False)
    monkeypatch.setattr(response_validation, "_reported", set())


def test_matching_payload_comes_back_unchanged():
    data = {"id": 1, "kind": 1, "child": {"id": 2, "extra": "kept"}, "other": [1]}

    result = validate_response(Parent, data, source="test")

    assert result == data
    assert type(result["kind"]) is int


def test_list_payload_is_validated_per_item():
    data = [{"id": 1}, {"id": 2}]

    assert validate_response(list[Child], data, source="test") == data


@pytest.mark.parametrize("empty", [{}, []])
def test_empty_error_payload_skips_validation(empty: object):
    assert validate_response(Parent, empty, source="test") is empty


def test_mismatch_raises_when_strict():
    with pytest.raises(ValidationError):
        validate_response(Parent, {"id": "x"}, source="test")


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
