from config import SENTRY_DSN
from utils import get_version


def init_sentry() -> None:
    """Start Sentry error reporting when a DSN is configured."""
    # Without a DSN the SDK reports nothing, yet init still loads every default
    # integration, which costs each process about 10 MB.
    if not SENTRY_DSN:
        return

    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, release=f"romm@{get_version()}")
