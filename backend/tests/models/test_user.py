import pytest

from handler.auth.constants import EDIT_SCOPES, FULL_SCOPES, WRITE_SCOPES
from models.user import User


def test_admin(admin_user: User):
    assert admin_user.oauth_scopes == FULL_SCOPES


def test_editor(editor_user: User):
    assert editor_user.oauth_scopes == EDIT_SCOPES


def test_user(viewer_user: User):
    assert viewer_user.oauth_scopes == WRITE_SCOPES


def test_a_bcrypt_hash_is_a_usable_password(viewer_user: User):
    assert viewer_user.has_password


@pytest.mark.parametrize(
    "hashed_password", [None, "", "8f14e45f-ceea-467a-9575-1a9b2e6c3d70"]
)
def test_a_missing_or_placeholder_hash_is_no_password(hashed_password: str | None):
    assert not User(username="oidc_user", hashed_password=hashed_password).has_password


@pytest.mark.parametrize(
    "oidc_enabled, oidc_sub, hashed_password, expected",
    [
        (True, "provider-sub", "$2b$12$hash", True),
        (True, None, "8f14e45f-ceea-467a-9575-1a9b2e6c3d70", True),
        (True, None, "$2b$12$hash", False),
        (False, "provider-sub", "$2b$12$hash", False),
    ],
)
def test_email_managed_by_oidc(
    mocker,
    oidc_enabled: bool,
    oidc_sub: str | None,
    hashed_password: str,
    expected: bool,
):
    mocker.patch("models.user.OIDC_ENABLED", oidc_enabled)
    user = User(username="u", oidc_sub=oidc_sub, hashed_password=hashed_password)

    assert user.email_managed_by_oidc is expected
