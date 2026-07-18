import pytest
from fastapi import status
from fastapi.testclient import TestClient

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory, TrackMeta
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_platform(slug: str) -> Platform:
    return db_platform_handler.add_platform(
        Platform(name=slug, slug=slug, fs_slug=slug)
    )


def _make_track(
    admin_id: int,
    platform: Platform,
    *,
    name: str,
    title: str,
    artist: str,
    album: str,
    genre: str,
    year: int,
    duration: float,
    cover_path: str | None = None,
    path_cover_l: str | None = None,
) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=f"{name}-slug",
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            path_cover_l=path_cover_l,
        )
    )
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_id)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=f"{title}.mp3",
            file_path=f"{rom.fs_path}/{name}/soundtrack",
            file_size_bytes=2048,
            category=RomFileCategory.SOUNDTRACK,
            track_meta=TrackMeta(
                rom_id=rom.id,
                title=title,
                artist=artist,
                album=album,
                genre=genre,
                year=year,
                duration_seconds=duration,
                has_embedded_cover=cover_path is not None,
                cover_path=cover_path,
            ),
        )
    )
    return rom


@pytest.fixture
def music_library(admin_user: User):
    pa = _make_platform("genesis")
    pb = _make_platform("nes")
    sonic = _make_track(
        admin_user.id,
        pa,
        name="Sonic",
        title="Green Hill",
        artist="Nakamura",
        album="Sonic OST",
        genre="Game",
        year=1991,
        duration=120.0,
        cover_path="roms/1/1/soundtrack/cover.jpg",
    )
    _make_track(
        admin_user.id,
        pa,
        name="Streets",
        title="Jingle",
        artist="Koshiro",
        album="SOR OST",
        genre="Dance",
        year=1992,
        duration=20.0,
        path_cover_l="roms/2/2/cover/big.png",
    )
    _make_track(
        admin_user.id,
        pb,
        name="Mario",
        title="Overworld",
        artist="Kondo",
        album="SMB OST",
        genre="Game",
        year=1985,
        duration=90.0,
    )
    # A rom with no soundtrack, to exercise the has_soundtrack filter.
    no_st = db_rom_handler.add_rom(
        Rom(
            platform_id=pb.id,
            name="Tetris",
            slug="tetris-slug",
            fs_name="Tetris.gb",
            fs_name_no_tags="Tetris",
            fs_name_no_ext="Tetris",
            fs_extension="gb",
            fs_path=f"{pb.slug}/roms",
        )
    )
    db_rom_handler.add_rom_user(rom_id=no_st.id, user_id=admin_user.id)
    return {"platform_a": pa, "platform_b": pb, "sonic": sonic, "no_soundtrack": no_st}


# ---------- /api/music/tracks ----------


def test_tracks_lists_all(client: TestClient, access_token: str, music_library):
    r = client.get("/api/music/tracks", headers=_auth(access_token))
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body["total"] == 3
    item = next(i for i in body["items"] if i["title"] == "Green Hill")
    assert item["year"] == 1991 and isinstance(item["year"], int)
    assert item["platform_slug"] == "genesis"
    assert item["stream_url"].endswith("/files/content/Green%20Hill.mp3")
    # track cover takes precedence
    assert item["cover_url"].endswith("/soundtrack/cover.jpg")


def test_tracks_cover_falls_back_to_game(
    client: TestClient, access_token: str, music_library
):
    r = client.get("/api/music/tracks?artist=koshiro", headers=_auth(access_token))
    item = r.json()["items"][0]
    assert item["cover_url"].endswith("/cover/big.png")


def test_tracks_artist_exact_case_insensitive(
    client: TestClient, access_token: str, music_library
):
    r = client.get("/api/music/tracks?artist=nakamura", headers=_auth(access_token))
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["artist"] == "Nakamura"


def test_tracks_search_substring(client: TestClient, access_token: str, music_library):
    r = client.get("/api/music/tracks?search=hill", headers=_auth(access_token))
    assert [i["title"] for i in r.json()["items"]] == ["Green Hill"]


def test_tracks_search_escapes_like_wildcards(
    client: TestClient, access_token: str, music_library
):
    wild = client.get("/api/music/tracks?search=hi_l", headers=_auth(access_token))
    assert wild.json()["total"] == 0
    literal = client.get("/api/music/tracks?search=hill", headers=_auth(access_token))
    assert [i["title"] for i in literal.json()["items"]] == ["Green Hill"]


def test_tracks_year_and_duration(client: TestClient, access_token: str, music_library):
    assert (
        client.get("/api/music/tracks?year=1992", headers=_auth(access_token)).json()[
            "total"
        ]
        == 1
    )
    # min_duration excludes the 20s jingle
    body = client.get(
        "/api/music/tracks?min_duration=60", headers=_auth(access_token)
    ).json()
    assert body["total"] == 2
    assert all(i["duration_seconds"] >= 60 for i in body["items"])


def test_tracks_platform_filter(client: TestClient, access_token: str, music_library):
    pid = music_library["platform_b"].id
    body = client.get(
        f"/api/music/tracks?platform_ids={pid}", headers=_auth(access_token)
    ).json()
    assert body["total"] == 1 and body["items"][0]["title"] == "Overworld"


def test_tracks_order_and_paginate(
    client: TestClient, access_token: str, music_library
):
    body = client.get(
        "/api/music/tracks?order_by=duration&order_dir=asc&limit=2",
        headers=_auth(access_token),
    ).json()
    assert body["total"] == 3 and len(body["items"]) == 2
    assert body["items"][0]["duration_seconds"] == 20.0


# ---------- facets ----------


def test_facet_artists_distinct_and_counts(
    client: TestClient, access_token: str, music_library
):
    body = client.get("/api/music/artists", headers=_auth(access_token)).json()
    assert body["total"] == 3
    assert {i["value"] for i in body["items"]} == {"Nakamura", "Koshiro", "Kondo"}
    assert all(i["count"] == 1 for i in body["items"])


def test_facet_artists_typeahead(client: TestClient, access_token: str, music_library):
    body = client.get(
        "/api/music/artists?search=ko", headers=_auth(access_token)
    ).json()
    assert {i["value"] for i in body["items"]} == {"Koshiro", "Kondo"}


def test_facet_artists_contextual(client: TestClient, access_token: str, music_library):
    pid = music_library["platform_b"].id
    body = client.get(
        f"/api/music/artists?platform_ids={pid}", headers=_auth(access_token)
    ).json()
    assert [i["value"] for i in body["items"]] == ["Kondo"]


def test_facet_years_are_ints(client: TestClient, access_token: str, music_library):
    body = client.get("/api/music/years", headers=_auth(access_token)).json()
    assert {i["value"] for i in body["items"]} == {1991, 1992, 1985}
    assert all(isinstance(i["value"], int) for i in body["items"])


def test_facet_years_typeahead(client: TestClient, access_token: str, music_library):
    body = client.get("/api/music/years?search=199", headers=_auth(access_token)).json()
    assert {i["value"] for i in body["items"]} == {1991, 1992}


# ---------- visibility (handler level) ----------


def test_tracks_excludes_hidden_platform(music_library):
    pb = music_library["platform_b"].id
    rows, total = db_rom_handler.get_music_tracks(hidden_platform_ids=[pb])
    assert total == 2
    assert all(r.platform_id != pb for r in rows)


def test_facet_excludes_hidden_platform(music_library):
    pb = music_library["platform_b"].id
    rows, total = db_rom_handler.get_music_facet(
        field="artists", hidden_platform_ids=[pb]
    )
    assert total == 2
    assert "Kondo" not in {r.value for r in rows}


# ---------- has_soundtrack roms filter ----------


def test_roms_has_soundtrack_filter(
    client: TestClient, access_token: str, music_library
):
    with_st = client.get(
        "/api/roms?has_soundtrack=true", headers=_auth(access_token)
    ).json()
    names = {i["name"] for i in with_st["items"]}
    assert "Sonic" in names and "Tetris" not in names

    without = client.get(
        "/api/roms?has_soundtrack=false", headers=_auth(access_token)
    ).json()
    assert "Tetris" in {i["name"] for i in without["items"]}
