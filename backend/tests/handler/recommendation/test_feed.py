from datetime import datetime, timedelta, timezone

import pytest

from handler.database import db_rom_handler
from handler.database.recommendations_handler import UserAffinityRow
from handler.recommendation.feed import (
    MIN_RECENCY_FACTOR,
    RECENCY_HALFLIFE_DAYS,
    _cache_key,
    seed_affinity,
)
from handler.redis_handler import sync_cache
from models.rom import RomUserStatus

NOW = datetime(2026, 8, 7, tzinfo=timezone.utc)


def affinity_row(**overrides) -> UserAffinityRow:
    defaults = {
        "rom_id": 1,
        "rating": None,
        "status": None,
        "last_played": NOW,
        "now_playing": False,
        "hidden": False,
        "playtime_ms": 0,
    }
    return UserAffinityRow(**{**defaults, **overrides})


def test_high_rating_produces_a_positive_seed():
    assert seed_affinity(affinity_row(rating=10), now=NOW) > 0


def test_low_rating_produces_a_negative_seed():
    # The point of a negative seed: steer the feed away from this kind of game.
    assert seed_affinity(affinity_row(rating=1), now=NOW) < 0


def test_midpoint_rating_is_roughly_neutral():
    assert seed_affinity(affinity_row(rating=5), now=NOW) == pytest.approx(0, abs=0.15)


def test_negative_seeds_are_damped_relative_to_positive_ones():
    liked = seed_affinity(affinity_row(rating=10), now=NOW)
    disliked = seed_affinity(affinity_row(rating=1), now=NOW)

    assert abs(disliked) < abs(liked)


def test_playtime_increases_affinity_with_diminishing_returns():
    hour = 3_600_000
    short = seed_affinity(affinity_row(playtime_ms=hour), now=NOW)
    medium = seed_affinity(affinity_row(playtime_ms=10 * hour), now=NOW)
    marathon = seed_affinity(affinity_row(playtime_ms=200 * hour), now=NOW)

    assert short < medium <= marathon
    # Saturation: 20h to 200h must matter far less than 1h to 10h.
    assert (marathon - medium) < (medium - short)


def test_completion_status_outweighs_merely_starting_a_game():
    completed = seed_affinity(
        affinity_row(status=RomUserStatus.COMPLETED_100.value), now=NOW
    )
    incomplete = seed_affinity(
        affinity_row(status=RomUserStatus.INCOMPLETE.value), now=NOW
    )

    assert completed > incomplete > 0


def test_now_playing_is_a_strong_signal():
    assert seed_affinity(affinity_row(now_playing=True), now=NOW) > seed_affinity(
        affinity_row(status=RomUserStatus.INCOMPLETE.value), now=NOW
    )


def test_recent_play_outweighs_an_old_one_of_equal_rating():
    recent = seed_affinity(affinity_row(rating=10, last_played=NOW), now=NOW)
    old = seed_affinity(
        affinity_row(rating=10, last_played=NOW - timedelta(days=365)), now=NOW
    )

    assert recent > old > 0


def test_recency_decay_halves_at_the_configured_halflife():
    fresh = seed_affinity(affinity_row(rating=10, last_played=NOW), now=NOW)
    halflife = seed_affinity(
        affinity_row(
            rating=10, last_played=NOW - timedelta(days=RECENCY_HALFLIFE_DAYS)
        ),
        now=NOW,
    )

    assert halflife == pytest.approx(fresh * 0.5, rel=0.01)


def test_old_favourites_never_decay_to_nothing():
    ancient = seed_affinity(
        affinity_row(rating=10, last_played=NOW - timedelta(days=3650)), now=NOW
    )

    assert ancient == pytest.approx(MIN_RECENCY_FACTOR, rel=0.01)


def test_naive_timestamps_are_treated_as_utc():
    # MariaDB hands back naive datetimes; a crash here would break the feed.
    naive = seed_affinity(
        affinity_row(rating=10, last_played=NOW.replace(tzinfo=None)), now=NOW
    )
    aware = seed_affinity(affinity_row(rating=10, last_played=NOW), now=NOW)

    assert naive == pytest.approx(aware)


def test_a_row_with_no_signals_at_all_contributes_nothing():
    assert seed_affinity(affinity_row(last_played=None), now=NOW) == 0.0


def test_a_played_but_unrated_game_still_seeds_weakly():
    weak = seed_affinity(affinity_row(last_played=NOW), now=NOW)
    rated = seed_affinity(affinity_row(rating=9, last_played=NOW), now=NOW)

    assert 0 < weak < rated


class TestFeedCacheInvalidation:
    """The cached ranking has to drop when the signals under it move.

    Every writer of `rom_user` goes through `update_rom_user`: play-session
    ingestion, save and state uploads, and the RetroAchievements sync all
    move `last_played` or `status` without touching the ROM endpoints, so
    invalidating at the endpoint left the feed stale for up to the cache TTL.
    """

    @staticmethod
    def _rom_user(rom, user):
        return db_rom_handler.get_rom_user(
            rom_id=rom.id, user_id=user.id
        ) or db_rom_handler.add_rom_user(rom_id=rom.id, user_id=user.id)

    @staticmethod
    def _seed_cache(user_id: int) -> None:
        sync_cache.set(_cache_key(user_id, 10), "[]")

    def test_a_play_updates_drops_the_cached_feed(self, rom, admin_user):
        rom_user = self._rom_user(rom, admin_user)
        self._seed_cache(admin_user.id)

        db_rom_handler.update_rom_user(
            rom_user.id, {"last_played": datetime.now(timezone.utc)}
        )

        assert sync_cache.get(_cache_key(admin_user.id, 10)) is None

    def test_an_unrelated_field_leaves_the_cache_alone(self, rom, admin_user):
        """Rebuilding a feed is not free, so only the scored fields drop it."""
        rom_user = self._rom_user(rom, admin_user)
        self._seed_cache(admin_user.id)

        db_rom_handler.update_rom_user(rom_user.id, {"difficulty": 3})

        assert sync_cache.get(_cache_key(admin_user.id, 10)) is not None
