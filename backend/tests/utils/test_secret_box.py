import pytest
from cryptography.fernet import Fernet

from utils.secret_box import UnsealError, seal, unseal


def test_a_sealed_value_opens_back_up():
    value = {"url": "https://discord.com/api/webhooks/1/token", "secret": None}

    sealed = seal(value)

    assert "token" not in sealed
    assert unseal(sealed) == value


def test_a_value_sealed_under_another_key_does_not_open():
    foreign = Fernet(Fernet.generate_key()).encrypt(b'{"url": "x"}').decode()

    with pytest.raises(UnsealError):
        unseal(foreign)


def test_plain_text_is_not_a_sealed_value():
    with pytest.raises(UnsealError):
        unseal("https://example.com/hook")
