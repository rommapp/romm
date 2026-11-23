from config import SENTRY_DSN
from utils import get_version


def init_sentry() -> None:
    """Start Sentry error reporting when a DSN is configured."""
    if not SENTRY_DSN:
        return

    # Imported here so a process without a DSN never loads the SDK.
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, release=f"romm@{get_version()}")
