"""Hidden and age-limited ROMs stay out of virtual collections and stats totals."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import update
from tests.factories import make_rom, make_save, make_screenshot, make_state

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth.base_handler import oauth_handler
from handler.database.base_handler import sync_session
from models.collection import VirtualCollection
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _auth(user: User) -> dict[str, str]:
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return {"Authorization": f"Bearer {token}"}


def _hide(entity: PermEntity, entity_id: int, user: User) -> None:
    with sync_session.begin() as session:
        session.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user.id))


def _genre_roms(platform: Platform, genre: str, count: int) -> list[Rom]:
    return [
        make_rom(platform, f"{genre} {index}", manual_metadata={"genres": [genre]})
        for index in range(count)
    ]


def _genre_id(name: str) -> str:
    return VirtualCollection(name=name, type="genre").id


def _genres(client: TestClient, user: User, **params: Any) -> dict[str, Any]:
    resp = client.get(
        "/api/collections/virtual",
        headers=_auth(user),
        params={"type": "genre", **params},
    )
    assert resp.status_code == status.HTTP_200_OK
    return {collection["name"]: collection for collection in resp.json()}


class TestVirtualCollections:
    @pytest.fixture
    def library(
        self,
        admin_user: User,
        viewer_user: User,
        platform: Platform,
        other_platform: Platform,
    ) -> dict[str, list[Rom]]:
        # "Aaa" sorts first, so a short page proves the limit follows the filter.
        library = {
            "Aaa Hidden": _genre_roms(other_platform, "Aaa Hidden", 3),
            "Bbb Partial": _genre_roms(platform, "Bbb Partial", 4),
            "Ccc Visible": _genre_roms(platform, "Ccc Visible", 3),
        }
        _hide(PermEntity.PLATFORMS, other_platform.id, viewer_user)
        _hide(PermEntity.ROMS, library["Bbb Partial"][0].id, viewer_user)
        return library

    def test_the_list_holds_only_visible_members(self, client, viewer_user, library):
        genres = _genres(client, viewer_user)

        assert sorted(genres) == ["Bbb Partial", "Ccc Visible"]
        partial = genres["Bbb Partial"]
        assert set(partial["rom_ids"]) == {rom.id for rom in library["Bbb Partial"][1:]}
        assert partial["rom_count"] == 3

    def test_the_limit_counts_only_visible_collections(
        self, client, viewer_user, library
    ):
        assert list(_genres(client, viewer_user, limit=1)) == ["Bbb Partial"]

    def test_one_visible_member_keeps_a_collection(self, client, viewer_user, library):
        for rom in library["Ccc Visible"][1:]:
            _hide(PermEntity.ROMS, rom.id, viewer_user)

        assert _genres(client, viewer_user)["Ccc Visible"]["rom_count"] == 1

    def test_a_member_spelled_differently_stays_in_its_collection(
        self, client, admin_user, viewer_user, platform
    ):
        # MariaDB's case-insensitive collation files all four under one name.
        roms = [
            make_rom(platform, f"rpg {index}", manual_metadata={"genres": [genre]})
            for index, genre in enumerate(["Rpg", "Rpg", "Rpg", "RPG"])
        ]
        _hide(PermEntity.ROMS, roms[0].id, viewer_user)

        every = _genres(client, admin_user)
        shown = _genres(client, viewer_user)

        assert {name: set(c["rom_ids"]) for name, c in shown.items()} == {
            name: set(c["rom_ids"]) - {roms[0].id} for name, c in every.items()
        }

    def test_the_admin_sees_every_member(self, client, admin_user, library):
        genres = _genres(client, admin_user)

        assert sorted(genres) == ["Aaa Hidden", "Bbb Partial", "Ccc Visible"]
        assert genres["Bbb Partial"]["rom_count"] == 4

    def test_identifiers_skip_hidden_collections(self, client, viewer_user, library):
        resp = client.get(
            "/api/collections/virtual/identifiers", headers=_auth(viewer_user)
        )

        assert resp.status_code == status.HTTP_200_OK
        assert _genre_id("Aaa Hidden") not in resp.json()
        assert _genre_id("Ccc Visible") in resp.json()

    def test_a_hidden_collection_reads_as_missing(self, client, viewer_user, library):
        resp = client.get(
            f"/api/collections/virtual/{_genre_id('Aaa Hidden')}",
            headers=_auth(viewer_user),
        )

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_a_partly_hidden_collection_drops_its_hidden_members(
        self, client, viewer_user, library
    ):
        resp = client.get(
            f"/api/collections/virtual/{_genre_id('Bbb Partial')}",
            headers=_auth(viewer_user),
        )

        assert resp.status_code == status.HTTP_200_OK
        assert set(resp.json()["rom_ids"]) == {
            rom.id for rom in library["Bbb Partial"][1:]
        }

    def test_the_age_rule_hides_unrated_members(self, client, viewer_user, library):
        with sync_session.begin() as session:
            session.execute(
                update(User)
                .where(User.id == viewer_user.id)
                .values(hide_unrated_roms=True)
            )

        assert _genres(client, viewer_user) == {}
        resp = client.get(
            f"/api/collections/virtual/{_genre_id('Ccc Visible')}",
            headers=_auth(viewer_user),
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_stats_asset_totals_skip_hidden_roms(
    client, admin_user, viewer_user, editor_user, platform, other_platform
):
    visible = make_rom(platform, "visible")
    hidden = make_rom(platform, "hidden")
    elsewhere = make_rom(other_platform, "elsewhere")
    for rom in (visible, hidden, elsewhere):
        make_save(rom, admin_user, f"{rom.name}.sav")
        make_state(rom, editor_user, f"{rom.name}.state")
        make_screenshot(rom, admin_user, f"{rom.name}.png")
    _hide(PermEntity.ROMS, hidden.id, viewer_user)
    _hide(PermEntity.PLATFORMS, other_platform.id, viewer_user)

    viewer_stats = client.get("/api/stats", headers=_auth(viewer_user)).json()
    admin_stats = client.get("/api/stats", headers=_auth(admin_user)).json()

    assert [viewer_stats[key] for key in ("SAVES", "STATES", "SCREENSHOTS")] == [
        1,
        1,
        1,
    ]
    assert [admin_stats[key] for key in ("SAVES", "STATES", "SCREENSHOTS")] == [
        3,
        3,
        3,
    ]
