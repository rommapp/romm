from handler.database import db_platform_handler
from models.platform import Platform


def test_rescan_preserves_user_authored_fields(platform):
    """A rescan merges a freshly built Platform over the existing row.

    The scan pipeline never populates `custom_name` or `description`, so both
    must survive the merge rather than being reset to their column defaults.
    """
    db_platform_handler.update_platform(
        platform.id,
        {
            "custom_name": "Sega - Genesis/ Mega Drive (Unofficial)",
            "description": "Aftermarket only",
        },
    )

    # Mirrors endpoints/sockets/scan.py: build a platform from scan metadata,
    # graft the existing id onto it, then merge.
    scanned = Platform(
        name=platform.name,
        slug=platform.slug,
        fs_slug=platform.fs_slug,
    )
    scanned.id = platform.id

    merged = db_platform_handler.add_platform(scanned)

    assert merged.custom_name == "Sega - Genesis/ Mega Drive (Unofficial)"
    assert merged.description == "Aftermarket only"
