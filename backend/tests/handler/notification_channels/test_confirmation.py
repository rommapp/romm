import itertools
import re

import pytest

from handler.email_handler import EmailError
from handler.notification_channels import confirmation
from handler.notification_channels.confirmation import (
    MAX_ATTEMPTS,
    CodeCooldownError,
    check_code,
    issue_code,
)

# The cache outlives a test, so each one confirms a channel of its own.
_channel_ids = itertools.count(900_000)


@pytest.fixture
def channel_id() -> int:
    return next(_channel_ids)


@pytest.fixture
def sent(mocker):
    return mocker.patch.object(confirmation, "send_email")


def _code_in(sent) -> str:
    text = sent.call_args.args[2]
    match = re.search(r"Your code is (\d{6})", text)
    assert match is not None
    return match.group(1)


async def test_the_emailed_code_confirms_once(channel_id, sent):
    await issue_code(channel_id, "a@example.com")
    code = _code_in(sent)

    assert sent.call_args.args[0] == "a@example.com"
    assert await check_code(channel_id, f" {code} ")
    assert not await check_code(channel_id, code)


async def test_too_many_misses_spend_the_code(channel_id, sent):
    await issue_code(channel_id, "a@example.com")
    code = _code_in(sent)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(MAX_ATTEMPTS):
        assert not await check_code(channel_id, wrong)

    assert not await check_code(channel_id, code)


async def test_another_code_has_to_wait(channel_id, sent):
    await issue_code(channel_id, "a@example.com")

    with pytest.raises(CodeCooldownError):
        await issue_code(channel_id, "a@example.com")


async def test_a_code_that_never_left_can_be_sent_again(channel_id, sent):
    sent.side_effect = EmailError("refused")
    with pytest.raises(EmailError):
        await issue_code(channel_id, "a@example.com")

    sent.side_effect = None
    await issue_code(channel_id, "a@example.com")

    assert await check_code(channel_id, _code_in(sent))
