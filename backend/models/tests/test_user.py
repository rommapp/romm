from utils.oauth import DEFAULT_SCOPES, WRITE_SCOPES, FULL_SCOPES

def test_admin(admin_user):
    admin_user.oauth_scopes == FULL_SCOPES

def test_editor(editor_user):
    editor_user.oauth_scopes == WRITE_SCOPES

def test_user(user):
    user.oauth_scopes == DEFAULT_SCOPES
