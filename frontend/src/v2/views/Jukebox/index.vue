<script setup lang="ts">
// Jukebox shell: owns the mode/URL state and the page chrome, and hands the
// screen to one of the three mode components.
import { RBtn, RChip, RDivider } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import musicApi, { type MusicTrackFilters } from "@/services/api/music";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import { useCan } from "@/v2/composables/useCan";
import { useJukeboxUrlState } from "@/v2/composables/useJukeboxUrlState";
import { useSoundtrackActions } from "@/v2/composables/useSoundtrackActions";
import {
  JUKEBOX_MODE_LABEL_KEYS,
  type JukeboxPlayerMode,
} from "@/v2/utils/jukebox";
import BrowseMode, { type BrowseEntry } from "./BrowseMode.vue";
import HomeMode from "./HomeMode.vue";
import SessionMode from "./SessionMode.vue";

const { t } = useI18n();
const canEdit = useCan("rom.edit");
const soundtrackActions = useSoundtrackActions();

const { mode, search, artist, genre, platform, decade, game, selectedDecade } =
  useJukeboxUrlState();

interface BrowseConfig {
  icon: string;
  searchable?: boolean;
  startShuffled?: boolean;
  selection: { value: string };
  loadEntries: (search: string) => Promise<BrowseEntry[]>;
  filterFor: (key: string) => MusicTrackFilters;
}

const BROWSE_MODES: Record<string, BrowseConfig> = {
  album: {
    icon: "mdi-album",
    searchable: true,
    selection: game,
    loadEntries: async (term) => {
      const { data } = await musicApi.getGames({ search: term });
      return data.items.map((item) => ({
        key: String(item.rom_id),
        label: item.name,
        subtitle: item.platform_name,
        coverUrl: item.cover_url ?? undefined,
        count: item.count,
      }));
    },
    filterFor: (key) => ({ romId: Number(key) }),
  },
  artist: {
    icon: "mdi-account-music",
    searchable: true,
    selection: artist,
    loadEntries: async (term) => {
      const { data } = await musicApi.getArtists({ search: term });
      return data.items.map((item) => ({
        key: String(item.value),
        label: String(item.value),
        count: item.count,
      }));
    },
    filterFor: (key) => ({ artist: key }),
  },
  genre: {
    icon: "mdi-shape",
    selection: genre,
    loadEntries: async () => {
      const { data } = await musicApi.getGameGenres();
      return data.items.map((item) => ({
        key: String(item.value),
        label: String(item.value),
        count: item.count,
      }));
    },
    filterFor: (key) => ({ gameGenre: key }),
  },
  platform: {
    icon: "mdi-controller-classic",
    selection: platform,
    loadEntries: async () => {
      const { data } = await musicApi.getPlatforms();
      return data.items.map((item) => ({
        key: String(item.id),
        label: item.name,
        platformSlug: item.slug,
        count: item.count,
      }));
    },
    filterFor: (key) => ({ platformIds: [Number(key)] }),
  },
  decade: {
    icon: "mdi-calendar-range",
    startShuffled: true,
    selection: decade,
    loadEntries: async () => {
      // The year facet is small, so decades are folded from it rather than
      // asking the server for a grouping only this screen wants.
      const { data } = await musicApi.getYears({ limit: 500 });
      const counts = new Map<number, number>();
      for (const item of data.items) {
        const year = Number(item.value);
        if (!Number.isFinite(year) || year <= 0) continue;
        const start = Math.floor(year / 10) * 10;
        counts.set(start, (counts.get(start) ?? 0) + item.count);
      }
      return [...counts.entries()]
        .sort((a, b) => b[0] - a[0])
        .map(([start, count]) => ({
          key: String(start),
          label: `${start}s`,
          count,
        }));
    },
    filterFor: (key) => ({
      minYear: Number(key),
      maxYear: Number(key) + 9,
    }),
  },
};

const browse = computed(() => BROWSE_MODES[mode.value] ?? null);

// The header names the open subgroup; the back arrow beside it leads home.
const headerTitle = computed(() =>
  mode.value === "home"
    ? t("common.jukebox")
    : t(JUKEBOX_MODE_LABEL_KEYS[mode.value]),
);

const SESSION_MODES = ["play-all", "station", "favorite", "recent"] as const;
type SessionMode = (typeof SESSION_MODES)[number];

const sessionMode = computed(() =>
  (SESSION_MODES as readonly string[]).includes(mode.value)
    ? (mode.value as SessionMode)
    : null,
);

function openMode(value: JukeboxPlayerMode) {
  mode.value = value;
}

function openHome() {
  mode.value = "home";
}

// Bumped after a delete so the active screen refetches the list it changed.
const refreshToken = ref(0);

async function deleteSoundtrack(fileId: number, romId: number) {
  if (await soundtrackActions.deleteTrack(romId, fileId))
    refreshToken.value += 1;
}
</script>

<template>
  <section class="jukebox">
    <div class="jukebox__header">
      <PageHeader :title="headerTitle">
        <template v-if="mode !== 'home'" #prepend>
          <RBtn
            icon="mdi-arrow-left"
            variant="text"
            :tooltip="t('common.back')"
            :aria-label="t('common.back')"
            @click="openHome"
          />
        </template>
        <template #count>
          <RChip size="x-small" color="primary">{{ t("common.beta") }}</RChip>
        </template>
      </PageHeader>
      <RDivider />
    </div>

    <HomeMode v-if="mode === 'home'" @open="openMode" />

    <BrowseMode
      v-else-if="browse"
      :key="mode"
      :icon="browse.icon"
      :searchable="browse.searchable"
      :start-shuffled="browse.startShuffled"
      :selected="browse.selection.value"
      :load-entries="browse.loadEntries"
      :filter-for="browse.filterFor"
      :refresh-token="refreshToken"
      :deletable="canEdit"
      @update:selected="browse.selection.value = $event"
      @delete-track="deleteSoundtrack"
    />

    <SessionMode
      v-else-if="sessionMode"
      :mode="sessionMode"
      :refresh-token="refreshToken"
      :deletable="canEdit"
      @delete-track="deleteSoundtrack"
    />
  </section>
</template>

<style scoped>
.jukebox {
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  display: grid;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}

.jukebox__header {
  grid-column: 1 / -1;
  padding: 24px var(--r-row-pad) 0;
}

html[data-bp~="sm-and-down"] .jukebox {
  grid-template-columns: minmax(210px, 36vw) minmax(0, 1fr);
}

html[data-bp~="xs"] .jukebox {
  height: calc(100dvh - var(--r-nav-h) - var(--r-bottom-nav-h));
  grid-template-columns: 76px minmax(0, 1fr);
}
</style>
