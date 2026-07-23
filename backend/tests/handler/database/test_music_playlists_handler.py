import pytest
from sqlalchemy.exc import IntegrityError

from handler.database import db_music_playlist_handler, db_rom_handler, db_user_handler
from models.music import MusicPlaylist
from models.rom import Rom, RomFile, RomFileCategory
from models.user import Role, User


@pytest.fixture
def playlist(admin_user: User) -> MusicPlaylist:
    return db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Focus", user_id=admin_user.id)
    )


@pytest.fixture
def track_ids(rom: Rom) -> list[int]:
    """Three soundtrack files on `rom`, referenced by id throughout."""
    return [
        db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=f"{name}.mp3",
                file_path=f"{rom.fs_path}/{rom.fs_name}",
                file_size_bytes=1,
                category=RomFileCategory.SOUNDTRACK,
            )
        ).id
        for name in ("aaa", "bbb", "ccc")
    ]


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


def test_add_tracks_positions_and_dedupe(track_ids, playlist: MusicPlaylist):
    aaa, bbb, ccc = track_ids
    added = db_music_playlist_handler.add_tracks_to_playlist(
        playlist.id, [aaa, bbb, aaa]
    )
    assert added == 2

    added = db_music_playlist_handler.add_tracks_to_playlist(playlist.id, [bbb, ccc])
    assert added == 1

    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [(e.rom_file_id, e.position) for e in entries] == [
        (aaa, 1),
        (bbb, 2),
        (ccc, 3),
    ]


def test_remove_tracks_keeps_order(track_ids, playlist: MusicPlaylist):
    aaa, bbb, ccc = track_ids
    db_music_playlist_handler.add_tracks_to_playlist(playlist.id, [aaa, bbb, ccc])
    removed = db_music_playlist_handler.remove_tracks_from_playlist(
        playlist.id, [bbb, 999999]
    )
    assert removed == 1
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [e.rom_file_id for e in entries] == [aaa, ccc]


def test_set_order_rewrites_and_appends_unlisted(track_ids, playlist: MusicPlaylist):
    aaa, bbb, ccc = track_ids
    db_music_playlist_handler.add_tracks_to_playlist(playlist.id, [aaa, bbb, ccc])
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    entry_id = {e.rom_file_id: e.id for e in entries}

    db_music_playlist_handler.set_playlist_track_order(
        playlist.id, [entry_id[ccc], entry_id[aaa]]
    )
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [(e.rom_file_id, e.position) for e in entries] == [
        (ccc, 0),
        (aaa, 1),
        (bbb, 2),
    ]


def test_track_counts(track_ids, playlist: MusicPlaylist, admin_user: User):
    other = db_music_playlist_handler.add_playlist(
        MusicPlaylist(name="Empty", user_id=admin_user.id)
    )
    db_music_playlist_handler.add_tracks_to_playlist(playlist.id, track_ids[:2])
    counts = db_music_playlist_handler.get_playlist_track_counts(
        [playlist.id, other.id]
    )
    assert counts == {playlist.id: 2}
    assert db_music_playlist_handler.get_playlist_track_counts([]) == {}


def test_favorites_add_remove_idempotent(track_ids, admin_user: User):
    aaa = track_ids[0]
    assert db_music_playlist_handler.add_favorite_tracks(admin_user.id, [aaa, aaa]) == 1
    assert db_music_playlist_handler.add_favorite_tracks(admin_user.id, [aaa]) == 0
    assert db_music_playlist_handler.remove_favorite_tracks(admin_user.id, [aaa]) == 1
    assert db_music_playlist_handler.remove_favorite_tracks(admin_user.id, [aaa]) == 0


def test_playlist_tracks_cascade_on_playlist_delete(track_ids, playlist: MusicPlaylist):
    db_music_playlist_handler.add_tracks_to_playlist(playlist.id, track_ids[:1])
    db_music_playlist_handler.delete_playlist(playlist.id)
    assert db_music_playlist_handler.get_playlist_entries(playlist.id) == []


def test_playlist_tracks_cascade_on_rom_file_delete(
    track_ids, playlist: MusicPlaylist, admin_user: User
):
    """A file that leaves the library takes its entries with it."""
    aaa, bbb, _ = track_ids
    db_music_playlist_handler.add_tracks_to_playlist(playlist.id, [aaa, bbb])
    db_music_playlist_handler.add_favorite_tracks(admin_user.id, [aaa])

    db_rom_handler.delete_rom_file(aaa)

    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    assert [e.rom_file_id for e in entries] == [bbb]
    assert db_music_playlist_handler.remove_favorite_tracks(admin_user.id, [aaa]) == 0
