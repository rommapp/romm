import importlib

import pytest


@pytest.fixture()
def reload_config(monkeypatch):
    """Reloads the `config` module after applying env overrides.

    The config module reads env vars at import time, so tests must reload it to
    validate URL building.
    """

    def _reload(**env_overrides):
        # Ensure required variables exist for config import.
        monkeypatch.setenv("ROMM_AUTH_SECRET_KEY", env_overrides.pop("ROMM_AUTH_SECRET_KEY", "test"))

        # Clean slate for Redis-related env vars.
        for key in (
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_USERNAME",
            "REDIS_PASSWORD",
            "REDIS_DB",
            "REDIS_SSL",
        ):
            monkeypatch.delenv(key, raising=False)

        for key, value in env_overrides.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(value))

        import config  # noqa: WPS433

        return importlib.reload(config)

    yield _reload

    # Restore module constants to the post-test environment.
    import config  # noqa: WPS433

    importlib.reload(config)


def test_redis_url_password_only_default_user(reload_config):
    cfg = reload_config(
        REDIS_HOST="redis",
        REDIS_PORT=6379,
        REDIS_PASSWORD="secret",
        REDIS_USERNAME="default",
        REDIS_DB=0,
        REDIS_SSL=False,
    )

    assert cfg.REDIS_URL == "redis://:secret@redis:6379/0"


def test_redis_url_acl_username_password(reload_config):
    cfg = reload_config(
        REDIS_HOST="redis",
        REDIS_PORT=6379,
        REDIS_USERNAME="romm",
        REDIS_PASSWORD="secret",
        REDIS_DB=2,
        REDIS_SSL=False,
    )

    assert cfg.REDIS_URL == "redis://romm:secret@redis:6379/2"


def test_redis_url_ssl_scheme(reload_config):
    cfg = reload_config(
        REDIS_HOST="redis",
        REDIS_PORT=6379,
        REDIS_PASSWORD="secret",
        REDIS_USERNAME="default",
        REDIS_DB=0,
        REDIS_SSL=True,
    )

    assert cfg.REDIS_URL == "rediss://:secret@redis:6379/0"
