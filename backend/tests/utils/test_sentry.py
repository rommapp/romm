from unittest.mock import patch

from utils import get_version
from utils.sentry import init_sentry


def test_init_sentry_skips_the_sdk_without_a_dsn():
    with (
        patch("utils.sentry.SENTRY_DSN", None),
        patch("sentry_sdk.init") as mock_init,
    ):
        init_sentry()

    mock_init.assert_not_called()


def test_init_sentry_starts_the_sdk_with_a_dsn():
    dsn = "https://key@sentry.example.com/1"
    with (
        patch("utils.sentry.SENTRY_DSN", dsn),
        patch("sentry_sdk.init") as mock_init,
    ):
        init_sentry()

    mock_init.assert_called_once_with(dsn=dsn, release=f"romm@{get_version()}")
