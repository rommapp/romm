<script setup lang="ts">
// Jukebox landing screen: two rows of launch tiles.
//
// Counts come from each facet's `total` (one cheap request per tile) rather
// than from grouping a downloaded catalog client-side.
import { RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import musicApi from "@/services/api/music";
import CardRow from "@/v2/components/shared/CardRow.vue";
import Tile from "@/v2/components/shared/Tile.vue";
import { FREE_RADIO_DURATION_SECONDS } from "@/v2/utils/freeRadio";
import type { JukeboxPlayerMode } from "@/v2/utils/jukebox";

const emit = defineEmits<{ (e: "open", mode: JukeboxPlayerMode): void }>();

const { t } = useI18n();

const totals = ref({
  tracks: 0,
  duration: 0,
  favorites: 0,
  games: 0,
  artists: 0,
  genres: 0,
  platforms: 0,
  decades: 0,
});

const RECENTLY_ADDED_LIMIT = 25;

async function facetTotal(
  load: (f: { limit: number }) => Promise<{ data: { total: number } }>,
): Promise<number> {
  try {
    const { data } = await load({ limit: 1 });
    return data.total;
  } catch {
    return 0;
  }
}

async function loadTotals() {
  const [stats, favorites, games, artists, genres, platforms, years] =
    await Promise.all([
      musicApi.getStats().catch(() => null),
      facetTotal(musicApi.getFavorites),
      facetTotal(musicApi.getGames),
      facetTotal(musicApi.getArtists),
      facetTotal(musicApi.getGameGenres),
      facetTotal(musicApi.getPlatforms),
      musicApi
        .getYears({ limit: 500 })
        .then(({ data }) => data.items)
        .catch(() => []),
    ]);

  const decades = new Set(
    years
      .map((year) => Number(year.value))
      .filter((year) => Number.isFinite(year) && year > 0)
      .map((year) => Math.floor(year / 10) * 10),
  );

  totals.value = {
    tracks: stats?.data.total_tracks ?? 0,
    duration: stats?.data.total_duration_seconds ?? 0,
    favorites,
    games,
    artists,
    genres,
    platforms,
    decades: decades.size,
  };
}

void loadTotals();

// The station plays at most an hour, so a small library caps at its own length.
const radioDuration = computed(() =>
  Math.min(totals.value.duration, FREE_RADIO_DURATION_SECONDS),
);

function minutes(seconds: number): string {
  return t("common.minutes-n", { n: Math.ceil(seconds / 60) });
}

function tracksCount(n: number): string {
  return t("rom.tracks-n", n, { named: { n } });
}

interface LaunchTile {
  mode: JukeboxPlayerMode;
  icon: string;
  label: string;
  count: string;
}

const launchRows = computed<{ title: string; tiles: LaunchTile[] }[]>(() => [
  {
    title: t("common.playlists"),
    tiles: [
      {
        mode: "station",
        icon: "mdi-radio-tower",
        label: t("common.free-radio"),
        count: minutes(radioDuration.value),
      },
      {
        mode: "decade",
        icon: "mdi-calendar-range",
        label: t("common.decade-mix"),
        count: t("common.decades-n", totals.value.decades, {
          named: { n: totals.value.decades },
        }),
      },
      {
        mode: "recent",
        icon: "mdi-clock-outline",
        label: t("common.recently-added-soundtracks"),
        count: tracksCount(Math.min(totals.value.tracks, RECENTLY_ADDED_LIMIT)),
      },
      {
        mode: "favorite",
        icon: "mdi-heart",
        label: t("common.favorite-soundtracks"),
        count: tracksCount(totals.value.favorites),
      },
    ],
  },
  {
    title: t("common.library"),
    tiles: [
      {
        mode: "play-all",
        icon: "mdi-playlist-music",
        label: t("common.play-all"),
        count: tracksCount(totals.value.tracks),
      },
      {
        mode: "album",
        icon: "mdi-album",
        label: t("common.music-by-album"),
        count: t("common.albums-n", totals.value.games, {
          named: { n: totals.value.games },
        }),
      },
      {
        mode: "platform",
        icon: "mdi-controller",
        label: t("common.soundtracks-by-platform"),
        count: t("common.platforms-n", totals.value.platforms, {
          named: { n: totals.value.platforms },
        }),
      },
      {
        mode: "artist",
        icon: "mdi-account-music",
        label: t("common.music-by-artist"),
        count: t("common.artists-n", totals.value.artists, {
          named: { n: totals.value.artists },
        }),
      },
      {
        mode: "genre",
        icon: "mdi-shape",
        label: t("common.soundtracks-by-genre"),
        count: t("common.genres-n", totals.value.genres, {
          named: { n: totals.value.genres },
        }),
      },
    ],
  },
]);
</script>

<template>
  <main class="jukebox__home">
    <CardRow
      v-for="row in launchRows"
      :key="row.title"
      :title="row.title"
      gap="16px"
    >
      <Tile
        v-for="tile in row.tiles"
        :key="tile.mode"
        density="compact"
        @click="emit('open', tile.mode)"
      >
        <template #icon>
          <RIcon :icon="tile.icon" size="52" />
        </template>
        {{ tile.label }}
        <template #count>{{ tile.count }}</template>
      </Tile>
    </CardRow>
  </main>
</template>

<style scoped>
.jukebox__home {
  grid-column: 1 / -1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  scrollbar-gutter: stable;
  padding: var(--r-space-5) 0 60px;
}

html[data-bp~="xs"] .jukebox__home {
  padding: var(--r-space-4) 0 40px;
}
</style>
