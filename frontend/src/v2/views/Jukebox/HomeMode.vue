<script setup lang="ts">
// Jukebox landing screen: two rows of launch tiles.
import { RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import musicApi from "@/services/api/music";
import CardRow from "@/v2/components/shared/CardRow.vue";
import Tile from "@/v2/components/shared/Tile.vue";
import { FREE_RADIO_DURATION_SECONDS } from "@/v2/utils/freeRadio";
import {
  JUKEBOX_MODE_LABEL_KEYS,
  RECENTLY_ADDED_LIMIT,
  type JukeboxPlayerMode,
} from "@/v2/utils/jukebox";

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

// Each tile fills in as its own query lands: some facets take seconds on a
// large catalog and no tile should wait on the slowest one.
function loadTotals() {
  void musicApi
    .getStats()
    .then(({ data }) => {
      totals.value.tracks = data.total_tracks;
      totals.value.duration = data.total_duration_seconds;
    })
    .catch(() => {});

  const facets = [
    ["favorites", musicApi.getFavorites],
    ["games", musicApi.getGames],
    ["artists", musicApi.getArtists],
    ["genres", musicApi.getGameGenres],
    ["platforms", musicApi.getPlatforms],
  ] as const;
  for (const [key, load] of facets) {
    void facetTotal(load).then((total) => {
      totals.value[key] = total;
    });
  }

  void musicApi
    .getYears({ limit: 500 })
    .then(({ data }) => {
      const decades = new Set(
        data.items
          .map((year) => Number(year.value))
          .filter((year) => Number.isFinite(year) && year > 0)
          .map((year) => Math.floor(year / 10) * 10),
      );
      totals.value.decades = decades.size;
    })
    .catch(() => {});
}

loadTotals();

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
        label: t(JUKEBOX_MODE_LABEL_KEYS.station),
        count: minutes(radioDuration.value),
      },
      {
        mode: "decade",
        icon: "mdi-calendar-range",
        label: t(JUKEBOX_MODE_LABEL_KEYS.decade),
        count: t("common.decades-n", totals.value.decades, {
          named: { n: totals.value.decades },
        }),
      },
      {
        mode: "recent",
        icon: "mdi-clock-outline",
        label: t(JUKEBOX_MODE_LABEL_KEYS.recent),
        count: tracksCount(Math.min(totals.value.tracks, RECENTLY_ADDED_LIMIT)),
      },
      {
        mode: "favorite",
        icon: "mdi-heart",
        label: t(JUKEBOX_MODE_LABEL_KEYS.favorite),
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
        label: t(JUKEBOX_MODE_LABEL_KEYS["play-all"]),
        count: tracksCount(totals.value.tracks),
      },
      {
        mode: "album",
        icon: "mdi-album",
        label: t(JUKEBOX_MODE_LABEL_KEYS.album),
        count: t("common.albums-n", totals.value.games, {
          named: { n: totals.value.games },
        }),
      },
      {
        mode: "platform",
        icon: "mdi-controller",
        label: t(JUKEBOX_MODE_LABEL_KEYS.platform),
        count: t("common.platforms-n", totals.value.platforms, {
          named: { n: totals.value.platforms },
        }),
      },
      {
        mode: "artist",
        icon: "mdi-account-music",
        label: t(JUKEBOX_MODE_LABEL_KEYS.artist),
        count: t("common.artists-n", totals.value.artists, {
          named: { n: totals.value.artists },
        }),
      },
      {
        mode: "genre",
        icon: "mdi-shape",
        label: t(JUKEBOX_MODE_LABEL_KEYS.genre),
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
          <span class="jukebox__tile-glyph">
            <RIcon :icon="tile.icon" size="30" />
          </span>
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

/* Neutral medallion behind each launch icon. */
.jukebox__tile-glyph {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-heading);
  background: var(--r-color-surface);
  box-shadow: inset 0 0 0 1px var(--r-color-border);
}

html[data-bp~="xs"] .jukebox__home {
  padding: var(--r-space-4) 0 40px;
}
</style>
