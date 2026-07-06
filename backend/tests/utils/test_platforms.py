from handler.database import db_platform_handler
from models.platform import Platform
from utils.platforms import get_supported_platforms


def test_supported_platform_not_shadowed_by_variant():
    """A variant/alias folder bound to a parent slug must not shadow the parent.

    Regression for the bug where adding an "fbneo" folder as a variant of
    "arcade" renamed the Arcade platform to "FBneo" in the platform picker.
    """
    # Canonical Arcade platform (folder name matches the slug).
    db_platform_handler.add_platform(
        Platform(name="Arcade", slug="arcade", fs_slug="arcade")
    )
    # Variant folder resolved to the same slug during scan.
    db_platform_handler.add_platform(
        Platform(name="FBneo", slug="arcade", fs_slug="fbneo")
    )

    supported = get_supported_platforms()
    arcade = next(p for p in supported if p.slug == "arcade")

    assert arcade.name == "Arcade"
    assert arcade.fs_slug == "arcade"
