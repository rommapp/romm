from handler.auth.base_handler import FULL_SCOPES, WRITE_SCOPES, DEFAULT_SCOPES


def test_admin(admin_user):
    admin_user.oauth_scopes == FULL_SCOPES


def test_editor(editor_user):
    editor_user.oauth_scopes == WRITE_SCOPES


def test_user(viewer_user):
    viewer_user.oauth_scopes == DEFAULT_SCOPES
