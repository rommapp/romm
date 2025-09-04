from datetime import timedelta

import pytest

from endpoints.auth import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from handler.auth import oauth_handler


@pytest.fixture()
def access_token(admin_user):  # noqa
    data = {
        "sub": admin_user.username,
        "iss": "romm:oauth",
        "scopes": " ".join(admin_user.oauth_scopes),
        "type": "access",
    }

    return oauth_handler.create_oauth_token(
        data=data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )


@pytest.fixture()
def refresh_token(admin_user):  # noqa
    data = {
        "sub": admin_user.username,
        "iss": "romm:oauth",
        "scopes": " ".join(admin_user.oauth_scopes),
        "type": "refresh",
    }

    return oauth_handler.create_oauth_token(
        data=data, expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
