import contextlib
import enum
import json
from typing import NotRequired, TypedDict
from unittest.mock import MagicMock

import pytest

from adapters.services.response_validation import (
    ResponseMismatchError,
    parse_response,
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


def test_matching_reply_decodes_to_what_was_sent():
    body = '{"id": 1, "kind": 1, "child": {"id": 2, "extra": "kept"}, "other": [1]}'

    result = parse_response(Parent, body, source="test")

    assert result == json.loads(body)
    assert result is not None
    assert type(result["kind"]) is int


def test_whole_number_for_a_float_matches():
    result = parse_response(
        Parent, b'{"id": 1, "kind": 0, "child": {"id": 2}, "score": 80}', source="test"
    )

    assert result is not None
    assert result.get("score") == 80


def test_list_reply_is_validated_per_item():
    assert parse_response(list[Child], b'[{"id": 1}, {"id": 2}]', source="test") == [
        {"id": 1},
        {"id": 2},
    ]


@pytest.mark.parametrize("body", [b"null", b"false", b"0", b'""', b"{}", b"[]"])
def test_a_reply_of_the_wrong_shape_is_a_mismatch(body: bytes):
    with pytest.raises(ResponseMismatchError):
        parse_response(Parent, body, source="test")


def test_a_value_that_fits_only_after_coercion_is_a_mismatch():
    with pytest.raises(ResponseMismatchError, match="id"):
        parse_response(
            Parent, b'{"id": "1", "kind": 0, "child": {"id": 2}}', source="test"
        )


def test_invalid_json_raises_a_decode_error():
    with pytest.raises(json.JSONDecodeError):
        parse_response(Parent, b"<html>", source="test")


def test_mismatch_is_not_swallowed_by_a_broad_except():
    with pytest.raises(ResponseMismatchError), contextlib.suppress(Exception):
        parse_response(Parent, b'{"id": "x"}', source="test")


def test_mismatch_returns_the_reply_as_sent_and_logs_once(lenient: MagicMock):
    body = b'[{"id": 1, "kind": 9, "child": {"id": 2}}]'

    first = parse_response(list[Parent], body, source="Provider endpoint")
    second = parse_response(list[Parent], body, source="Provider endpoint")

    assert first == second == json.loads(body)
    lenient.warning.assert_called_once()
    message = lenient.warning.call_args.args[0] % lenient.warning.call_args.args[1:]
    assert "Provider endpoint" in message
    assert "*.kind" in message


def test_id_keyed_entries_share_one_warning(lenient: MagicMock):
    parse_response(dict[str, Child], b'{"101": {"id": "x"}}', source="test")
    parse_response(dict[str, Child], b'{"202": {"id": "y"}}', source="test")

    lenient.warning.assert_called_once()


def test_known_problems_in_a_new_combination_are_not_logged_again(
    lenient: MagicMock,
):
    parse_response(list[Child], b'[{"id": "x"}]', source="test")
    parse_response(list[Child], b"[{}]", source="test")
    parse_response(list[Child], b'[{"id": "x"}, {}]', source="test")

    assert lenient.warning.call_count == 2


def test_a_reply_whose_top_level_is_the_wrong_type_reads_as_none(lenient: MagicMock):
    assert parse_response(Parent, b"[1, 2]", source="test") is None
    lenient.warning.assert_called_once()
