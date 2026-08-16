from datetime import datetime, timedelta, timezone

from handler.database import db_download_handler, db_rom_handler
from models.download_event import DownloadKind, DownloadSource
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User


def _add_rom(platform: Platform, index: int, size_bytes: int = 1000) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=f"dl_rom_{index}",
            slug=f"dl_rom_{index}",
            fs_name=f"dl_rom_{index}.zip",
            fs_name_no_tags=f"dl_rom_{index}",
            fs_name_no_ext=f"dl_rom_{index}",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=f"dl_rom_{index}.zip",
            file_path=rom.fs_path,
            file_size_bytes=size_bytes,
        )
    )
    return rom


def _record(rom: Rom, user: User | None = None, **kwargs):
    return db_download_handler.record_download(
        rom=rom,
        user_id=user.id if user else None,
        username=user.username if user else "anonymous",
        source=kwargs.pop("source", DownloadSource.WEBUI),
        kind=kwargs.pop("kind", DownloadKind.ROM),
        file_count=kwargs.pop("file_count", 1),
        size_bytes=kwargs.pop("size_bytes", 1000),
        **kwargs,
    )


def test_record_download_bumps_rom_counters(rom: Rom, admin_user: User):
    assert rom.download_count == 0
    assert rom.last_downloaded_at is None

    _record(rom, admin_user)
    _record(rom, admin_user)

    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    assert refreshed.download_count == 2
    assert refreshed.last_downloaded_at is not None


def test_record_download_snapshots_identity(rom: Rom, admin_user: User):
    event = _record(rom, admin_user, client_ip="10.0.0.5", user_agent="pytest/1.0")

    assert event.username == admin_user.username
    assert event.rom_name == rom.name
    assert event.platform_name == rom.platform_display_name
    assert event.client_ip == "10.0.0.5"
    assert event.user_agent == "pytest/1.0"


def test_record_download_allows_anonymous(rom: Rom):
    event = _record(rom, None, source=DownloadSource.ANONYMOUS)

    assert event.user_id is None
    assert event.username == "anonymous"


def test_get_download_log_is_newest_first_and_paginates(rom: Rom, admin_user: User):
    for _ in range(3):
        _record(rom, admin_user)

    page = db_download_handler.get_download_log(limit=2, offset=0)
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["items"][0]["id"] > page["items"][1]["id"]

    second = db_download_handler.get_download_log(limit=2, offset=2)
    assert len(second["items"]) == 1


def test_get_download_log_filters_by_source(rom: Rom, admin_user: User):
    _record(rom, admin_user, source=DownloadSource.WEBUI)
    _record(rom, admin_user, source=DownloadSource.CLIENT_TOKEN)

    page = db_download_handler.get_download_log(source=DownloadSource.CLIENT_TOKEN)
    assert page["total"] == 1
    assert page["items"][0]["source"] == "client_token"


def test_get_download_log_clamps_page_size(rom: Rom, admin_user: User):
    _record(rom, admin_user)

    page = db_download_handler.get_download_log(limit=10_000, offset=-5)
    assert page["limit"] == 200
    assert page["offset"] == 0


def test_get_summary_counts_totals_and_unused(
    platform: Platform, admin_user: User, rom: Rom
):
    downloaded = _add_rom(platform, 1, size_bytes=2048)
    _add_rom(platform, 2, size_bytes=4096)  # never downloaded

    _record(downloaded, admin_user, size_bytes=2048)

    summary = db_download_handler.get_summary()

    assert summary["total_downloads"] == 1
    assert summary["total_bytes"] == 2048
    assert summary["unique_roms_downloaded"] == 1
    assert summary["unique_users"] == 1
    # The `rom` fixture and dl_rom_2 both have zero downloads; only dl_rom_2
    # has files, so it alone contributes bytes.
    assert summary["never_downloaded_count"] == 2
    assert summary["never_downloaded_bytes"] == 4096


def test_get_summary_window_excludes_older_events(rom: Rom, admin_user: User):
    _record(rom, admin_user)

    future = datetime.now(timezone.utc) + timedelta(days=1)
    summary = db_download_handler.get_summary(since=future)

    assert summary["total_downloads"] == 1
    assert summary["downloads_in_window"] == 0


def test_get_top_roms_ranks_by_count(platform: Platform, admin_user: User):
    quiet = _add_rom(platform, 1)
    popular = _add_rom(platform, 2)

    _record(quiet, admin_user)
    for _ in range(3):
        _record(popular, admin_user)

    top = db_download_handler.get_top_roms(limit=10)

    assert [r["rom_id"] for r in top] == [popular.id, quiet.id]
    assert top[0]["download_count"] == 3
    assert top[0]["platform_name"] == platform.name


def test_get_top_roms_excludes_never_downloaded(platform: Platform, admin_user: User):
    _add_rom(platform, 1)
    downloaded = _add_rom(platform, 2)
    _record(downloaded, admin_user)

    top = db_download_handler.get_top_roms()

    assert [r["rom_id"] for r in top] == [downloaded.id]


def test_get_downloads_by_platform_and_source(rom: Rom, admin_user: User):
    _record(rom, admin_user, source=DownloadSource.WEBUI, size_bytes=500)
    _record(rom, admin_user, source=DownloadSource.WEBUI, size_bytes=500)
    _record(rom, admin_user, source=DownloadSource.OAUTH, size_bytes=250)

    by_platform = db_download_handler.get_downloads_by_platform()
    assert len(by_platform) == 1
    assert by_platform[0]["download_count"] == 3
    assert by_platform[0]["size_bytes"] == 1250

    by_source = db_download_handler.get_downloads_by_source()
    counts = {row["source"]: row["count"] for row in by_source}
    assert counts == {"webui": 2, "oauth": 1}


def test_get_timeline_gap_fills_days(rom: Rom, admin_user: User):
    _record(rom, admin_user)

    timeline = db_download_handler.get_timeline(days=7)

    assert len(timeline) == 7
    assert timeline[-1]["count"] == 1
    assert all(point["count"] == 0 for point in timeline[:-1])


def test_prune_events_older_than_deletes_only_stale_rows(rom: Rom, admin_user: User):
    old = _record(rom, admin_user)
    recent = _record(rom, admin_user)

    # Backdate one event past the retention window.
    db_download_handler.prune_events_older_than(
        datetime.now(timezone.utc) - timedelta(days=3650)
    )
    assert db_download_handler.get_download_log()["total"] == 2

    from handler.database.base_handler import sync_session
    from models.download_event import DownloadEvent

    with sync_session.begin() as s:
        s.query(DownloadEvent).filter(DownloadEvent.id == old.id).update(
            {"downloaded_at": datetime.now(timezone.utc) - timedelta(days=90)}
        )

    deleted = db_download_handler.prune_events_older_than(
        datetime.now(timezone.utc) - timedelta(days=30)
    )

    assert deleted == 1
    page = db_download_handler.get_download_log()
    assert page["total"] == 1
    assert page["items"][0]["id"] == recent.id


def test_prune_events_leaves_rom_counters_alone(rom: Rom, admin_user: User):
    # The counter is a lifetime total; trimming the audit log must not rewrite
    # what the game page shows.
    _record(rom, admin_user)
    _record(rom, admin_user)

    db_download_handler.prune_events_older_than(datetime.now(timezone.utc))

    assert db_download_handler.get_download_log()["total"] == 0
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    assert refreshed.download_count == 2


def test_resync_rom_counters_rebuilds_from_log(rom: Rom, admin_user: User):
    _record(rom, admin_user)
    _record(rom, admin_user)

    # Simulate drift (restored backup, manual edit).
    db_rom_handler.update_rom(rom.id, {"download_count": 99})

    assert db_download_handler.resync_rom_counters() == 1

    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    assert refreshed.download_count == 2
