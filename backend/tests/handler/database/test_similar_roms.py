"""Tests for the metadata-overlap "similar games in your library" ranking.

`get_similar_rom_candidates` reads the `roms_metadata` DB view (derived from
the per-provider JSON columns), so candidates are seeded by writing
`igdb_metadata` rather than inserting into the view. Similarity is a weighted
overlap of franchises / collections / genres / companies / age ratings, with a
same-platform multiplier, excluding the ROM itself and its siblings. It returns
`(rom_id, platform_id)` pairs (user-independent and cached); per-user
visibility filtering and the result limit are applied by the endpoint.
"""

import pytest

from handler.database import db_platform_handler, db_rom_handler
from models.platform import Platform
from models.rom import Rom
from models.user import User


@pytest.fixture
def other_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(name="other", slug="other_slug", fs_slug="other_slug")
    )


def _add_rom(
    platform: Platform,
    name: str,
    *,
    igdb_id: int | None = None,
    igdb_metadata: dict | None = None,
) -> Rom:
    rom = Rom(
        platform_id=platform.id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        fs_name=f"{name}.zip",
        fs_path=f"{platform.slug}/roms",
        igdb_id=igdb_id,
        igdb_metadata=igdb_metadata or {},
    )
    return db_rom_handler.add_rom(rom)


def _ids(candidates: list[tuple[int, int]]) -> list[int]:
    return [rom_id for rom_id, _ in candidates]


class TestGetSimilarRomCandidates:
    def test_ranks_by_weighted_overlap_and_platform_boost(
        self, platform: Platform, other_platform: Platform, admin_user: User
    ):
        target = _add_rom(
            platform,
            "Zelda Target",
            igdb_id=1000,
            igdb_metadata={
                "franchises": ["Zelda"],
                "genres": ["Adventure"],
                "companies": ["Nintendo"],
            },
        )

        # Same franchise + same platform -> franchise (5) * boost (1.25).
        same_platform_franchise = _add_rom(
            platform,
            "Zelda Same Platform",
            igdb_id=1001,
            igdb_metadata={"franchises": ["Zelda"]},
        )
        # Same franchise, different platform -> franchise (5), no boost.
        cross_platform_franchise = _add_rom(
            other_platform,
            "Zelda Cross Platform",
            igdb_id=1002,
            igdb_metadata={"franchises": ["Zelda"]},
        )
        # Shared genre only -> genre (3).
        genre_only = _add_rom(
            other_platform,
            "Some Adventure",
            igdb_id=1003,
            igdb_metadata={"genres": ["Adventure"]},
        )
        # No overlap -> excluded entirely.
        _add_rom(
            platform,
            "Unrelated Racer",
            igdb_id=1004,
            igdb_metadata={"genres": ["Racing"]},
        )

        result = db_rom_handler.get_similar_rom_candidates(target)

        assert _ids(result) == [
            same_platform_franchise.id,
            cross_platform_franchise.id,
            genre_only.id,
        ]

    def test_excludes_siblings(self, platform: Platform, admin_user: User):
        target = _add_rom(
            platform,
            "Zelda Target",
            igdb_id=2000,
            igdb_metadata={"franchises": ["Zelda"]},
        )
        # Same platform + same igdb_id -> sibling (same game, other dump).
        sibling = _add_rom(
            platform,
            "Zelda Target (Rev 1)",
            igdb_id=2000,
            igdb_metadata={"franchises": ["Zelda"]},
        )
        real_match = _add_rom(
            platform,
            "Zelda Other",
            igdb_id=2001,
            igdb_metadata={"franchises": ["Zelda"]},
        )

        # Exclusion must hold in both directions of the sibling pairing:
        # neither dump should surface the other as "similar".
        assert _ids(db_rom_handler.get_similar_rom_candidates(target)) == [
            real_match.id
        ]
        assert _ids(db_rom_handler.get_similar_rom_candidates(sibling)) == [
            real_match.id
        ]

    def test_returns_empty_without_metadata(self, platform: Platform, admin_user: User):
        target = _add_rom(platform, "No Metadata", igdb_id=3000)
        _add_rom(
            platform,
            "Has Metadata",
            igdb_id=3001,
            igdb_metadata={"franchises": ["Zelda"]},
        )

        assert db_rom_handler.get_similar_rom_candidates(target) == []

    def test_returns_platform_ids_for_visibility_filtering(
        self, platform: Platform, other_platform: Platform, admin_user: User
    ):
        target = _add_rom(
            platform,
            "Zelda Target",
            igdb_id=5000,
            igdb_metadata={"franchises": ["Zelda"]},
        )
        same_platform = _add_rom(
            platform,
            "Zelda Same Platform",
            igdb_id=5001,
            igdb_metadata={"franchises": ["Zelda"]},
        )
        other = _add_rom(
            other_platform,
            "Zelda Other Platform",
            igdb_id=5002,
            igdb_metadata={"franchises": ["Zelda"]},
        )

        # Each candidate carries its platform id so the endpoint can drop
        # hidden platforms without re-querying.
        result = dict(db_rom_handler.get_similar_rom_candidates(target))

        assert result[same_platform.id] == platform.id
        assert result[other.id] == other_platform.id
