import pytest
from sqlalchemy.exc import IntegrityError

from handler.database import db_music_playlist_handler, db_user_handler
from models.music import MusicPlaylist
from models.user import Role, User


@pytest.fixture
def playlist(admin_user: User) -> MusicPlaylist:
    return db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Focus", user_id=admin_user.id)
    )


def test_playlist_crud(admin_user: User, playlist: MusicPlaylist):
    assert db_music_playlist_handler.get_playlist(playlist.id).name == "Focus"
    assert (
        db_music_playlist_handler.get_playlist_by_name("Focus", admin_user.id).id
        == playlist.id
    )
    assert db_music_playlist_handler.get_playlist_by_name("Focus", 999999) is None

    updated = db_music_playlist_handler.update_playlist(
        playlist.id, {"description": "deep work", "is_public": True}
    )
    assert updated.description == "deep work" and updated.is_public is True

    db_music_playlist_handler.delete_playlist(playlist.id)
    assert db_music_playlist_handler.get_playlist(playlist.id) is None


def test_playlist_name_unique_per_user(admin_user: User, playlist: MusicPlaylist):
    with pytest.raises(IntegrityError):
        db_music_playlist_handler.add_playlist(
            MusicPlaylist(name="Focus", user_id=admin_user.id)
        )


def test_playlist_same_name_other_user(playlist: MusicPlaylist):
    other = db_user_handler.add_user(
        User(
            username="second",
            hashed_password="x",
            email="second@example.com",
            enabled=True,
            role=Role.USER,
        )
    )
    dup = db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Focus", user_id=other.id)
    )
    assert dup.id != playlist.id


def test_get_playlists_own_and_public(admin_user: User, playlist: MusicPlaylist):
    other = db_user_handler.add_user(
        User(
            username="second",
            hashed_password="x",
            email="second@example.com",
            enabled=True,
            role=Role.USER,
        )
    )
    db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Private", user_id=other.id)
    )
    public = db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Shared", user_id=other.id, is_public=True)
    )

    visible = db_music_playlist_handler.get_playlists(admin_user.id)
    assert {p.id for p in visible} == {playlist.id, public.id}


def test_add_tracks_positions_and_dedupe(rom, playlist: MusicPlaylist):
    added = db_music_playlist_handler.add_tracks_to_playlist(
        playlist.id, [(rom.id, "aaa"), (rom.id, "bbb"), (rom.id, "aaa")]
    )
    assert added == 2

    added = db_music_playlist_handler.add_tracks_to_playlist(
        playlist.id, [(rom.id, "bbb"), (rom.id, "ccc")]
    )
    assert added == 1

    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [(e.md5_hash, e.position) for e in entries] == [
        ("aaa", 1),
        ("bbb", 2),
        ("ccc", 3),
    ]


def test_remove_tracks_keeps_order(rom, playlist: MusicPlaylist):
    db_music_playlist_handler.add_tracks_to_playlist(
        playlist.id, [(rom.id, "aaa"), (rom.id, "bbb"), (rom.id, "ccc")]
    )
    removed = db_music_playlist_handler.remove_tracks_from_playlist(
        playlist.id, [(rom.id, "bbb"), (rom.id, "zzz")]
    )
    assert removed == 1
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [e.md5_hash for e in entries] == ["aaa", "ccc"]


def test_set_order_rewrites_and_appends_unlisted(rom, playlist: MusicPlaylist):
    db_music_playlist_handler.add_tracks_to_playlist(
        playlist.id, [(rom.id, "aaa"), (rom.id, "bbb"), (rom.id, "ccc")]
    )
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    by_md5 = {e.md5_hash: e.id for e in entries}

    db_music_playlist_handler.set_playlist_track_order(
        playlist.id, [by_md5["ccc"], by_md5["aaa"]]
    )
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [(e.md5_hash, e.position) for e in entries] == [
        ("ccc", 0),
        ("aaa", 1),
        ("bbb", 2),
    ]


def test_track_counts(rom, playlist: MusicPlaylist, admin_user: User):
    other = db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Empty", user_id=admin_user.id)
    )
    db_music_playlist_handler.add_tracks_to_playlist(
        playlist.id, [(rom.id, "aaa"), (rom.id, "bbb")]
    )
    counts = db_music_playlist_handler.get_playlist_track_counts(
        [playlist.id, other.id]
    )
    assert counts == {playlist.id: 2}
    assert db_music_playlist_handler.get_playlist_track_counts([]) == {}


def test_favorites_add_remove_idempotent(rom, admin_user: User):
    assert (
        db_music_playlist_handler.add_favorite_tracks(
            admin_user.id, [(rom.id, "aaa"), (rom.id, "aaa")]
        )
        == 1
    )
    assert (
        db_music_playlist_handler.add_favorite_tracks(admin_user.id, [(rom.id, "aaa")])
        == 0
    )
    assert (
        db_music_playlist_handler.remove_favorite_tracks(
            admin_user.id, [(rom.id, "aaa")]
        )
        == 1
    )
    assert (
        db_music_playlist_handler.remove_favorite_tracks(
            admin_user.id, [(rom.id, "aaa")]
        )
        == 0
    )


def test_playlist_tracks_cascade_on_playlist_delete(rom, playlist: MusicPlaylist):
    db_music_playlist_handler.add_tracks_to_playlist(playlist.id, [(rom.id, "aaa")])
    db_music_playlist_handler.delete_playlist(playlist.id)
    assert db_music_playlist_handler.get_playlist_entries(playlist.id) == []
