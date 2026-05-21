<script setup lang="ts">
// GameDetails — artist-mockup layout.
//
// Two-column body: fixed cover column on the left, everything else (header,
// tabs, tab panel) stacked in a flex-1 column on the right. Thin
// orchestrator — data + tab state live here, every visual piece is a
// sub-component under components/GameDetails/.
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import type { IGDBRelatedGame } from "@/__generated__";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import { toBrowserLocale } from "@/utils";
import AchievementsTab from "@/v2/components/GameDetails/AchievementsTab.vue";
import CoverColumn from "@/v2/components/GameDetails/CoverColumn.vue";
import GameHeader from "@/v2/components/GameDetails/GameHeader.vue";
import type { InfoGridSection } from "@/v2/components/GameDetails/InfoGrid.vue";
import MediaTab from "@/v2/components/GameDetails/MediaTab.vue";
import MetadataTab from "@/v2/components/GameDetails/MetadataTab.vue";
import NotesTab from "@/v2/components/GameDetails/NotesTab.vue";
import OverviewTab from "@/v2/components/GameDetails/OverviewTab.vue";
import SaveDataTab from "@/v2/components/GameDetails/SaveDataTab.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

const route = useRoute();
const router = useRouter();
const romsStore = storeRoms();
const heartbeatStore = storeHeartbeat();
const authStore = storeAuth();
const { currentRom } = storeToRefs(romsStore);
const { toWebp } = useWebpSupport();
const { locale } = useI18n();

const setBgArt = useBackgroundArt();

// Active tab — URL-persistent via `?tab=`.
const tab = ref<string>((route.query.tab as string) || "overview");
watch(tab, (value) => {
  if (route.query.tab !== value) {
    router.replace({
      path: route.path,
      query: { ...route.query, tab: value },
    });
  }
});
watch(
  () => route.query.tab,
  (value) => {
    if (typeof value === "string" && value !== tab.value) {
      tab.value = value;
    }
  },
);

const title = computed(() => {
  const r = currentRom.value;
  if (!r) return "";
  return r.name || r.fs_name_no_ext;
});

const platformLabel = computed(() => {
  const r = currentRom.value;
  if (!r) return "";
  return r.platform_custom_name || r.platform_display_name;
});

const releaseDate = computed(() => {
  const ts = currentRom.value?.metadatum?.first_release_date;
  if (!ts) return null;
  return new Date(Number(ts)).toLocaleDateString(
    toBrowserLocale(locale.value),
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    },
  );
});

const genres = computed(() => currentRom.value?.metadatum?.genres ?? []);
const franchises = computed(
  () => currentRom.value?.metadatum?.franchises ?? [],
);
const companies = computed(() => currentRom.value?.metadatum?.companies ?? []);
const collections = computed(
  () => currentRom.value?.metadatum?.collections ?? [],
);

const regions = computed(() => currentRom.value?.regions ?? []);
const languages = computed(() => currentRom.value?.languages ?? []);
const tags = computed(() => currentRom.value?.tags ?? []);

const verified = computed(() => Boolean(currentRom.value?.crc_hash));

const coverPath = computed(() => {
  const r = currentRom.value;
  if (!r) return null;
  const path = r.path_cover_large ?? r.path_cover_small ?? null;
  return path ? toWebp(path) : null;
});

const coverFallback = computed(() => currentRom.value?.url_cover ?? null);
const resolvedCover = computed(() => coverPath.value ?? coverFallback.value);

watch(
  resolvedCover,
  (url) => {
    if (url) setBgArt(url);
  },
  { immediate: true },
);

const canPlayEJS = computed(() => {
  const emu = heartbeatStore.value?.EMULATION;
  return Boolean(emu && !emu.DISABLE_EMULATOR_JS);
});

const lastPlayed = computed(() => {
  const ts = currentRom.value?.rom_user?.last_played;
  if (!ts) return null;
  return new Date(ts).toLocaleString();
});

// "Companies" (not "Developer") — the API field is a merged list of
// developers + publishers + other company roles produced by the backend
// (see flashpoint/gamelist/launchbox handlers); calling it Developer
// would be a lie. "Franchises" mirrors the singular→plural consistency
// of the surrounding rows.
const overviewSections = computed<InfoGridSection[]>(() => [
  { label: "Genres", items: genres.value },
  { label: "Companies", items: companies.value },
  { label: "Franchises", items: franchises.value },
  { label: "Collections", items: collections.value },
]);

const playerCount = computed<string | null>(() => {
  const pc = currentRom.value?.metadatum?.player_count;
  return pc ? pc.trim() : null;
});
const userCollections = computed(
  () => currentRom.value?.user_collections ?? [],
);

const raMetadata = computed(() => currentRom.value?.merged_ra_metadata ?? null);
const achievementsTotal = computed(
  () => raMetadata.value?.achievements?.length ?? 0,
);

// User's earned-achievements for this ROM. Same shape as v1: locate the
// matching `RAUserGameProgression` in the auth user's bundle by
// `rom_ra_id`, then index its `earned_achievements` by `id`
// (== achievement.badge_id) so the tab can do O(1) per-row lookups.
const earnedAchievementIds = computed<ReadonlySet<string>>(() => {
  const romRaId = currentRom.value?.ra_id;
  if (!romRaId) return new Set<string>();
  const progression = authStore.user?.ra_progression?.results?.find(
    (r) => r.rom_ra_id === romRaId,
  );
  return new Set((progression?.earned_achievements ?? []).map((e) => e.id));
});
const achievementsEarned = computed(() => earnedAchievementIds.value.size);

const igdb = computed(() => currentRom.value?.igdb_metadata ?? null);
const similarGames = computed<IGDBRelatedGame[]>(
  () => igdb.value?.similar_games ?? [],
);
const remakes = computed<IGDBRelatedGame[]>(() => igdb.value?.remakes ?? []);
const remasters = computed<IGDBRelatedGame[]>(
  () => igdb.value?.remasters ?? [],
);
const expansions = computed<IGDBRelatedGame[]>(
  () => igdb.value?.expansions ?? [],
);
const dlcs = computed<IGDBRelatedGame[]>(() => igdb.value?.dlcs ?? []);

const savesCount = computed(() => currentRom.value?.user_saves?.length ?? 0);
const statesCount = computed(() => currentRom.value?.user_states?.length ?? 0);
const saveDataCount = computed(() => savesCount.value + statesCount.value);

const tabs = computed<RTabNavItem[]>(() => [
  { id: "overview", label: "Overview" },
  { id: "media", label: "Media" },
  { id: "notes", label: "Notes" },
  {
    id: "achievements",
    label: "Achievements",
    badge: `${achievementsEarned.value}/${achievementsTotal.value}`,
  },
  {
    id: "save-data",
    label: "Save data",
    badge: saveDataCount.value,
  },
  { id: "metadata", label: "Metadata" },
]);
</script>

<template>
  <section v-if="currentRom" class="r-v2-det">
    <div class="r-v2-det__body">
      <CoverColumn :src="resolvedCover" :alt="title" :rom-id="currentRom.id" />

      <div class="r-v2-det__info">
        <GameHeader
          :rom="currentRom"
          :title="title"
          :platform-label="platformLabel"
          :release-date="releaseDate"
          :verified="verified"
          :regions="regions"
          :languages="languages"
          :tags="tags"
          :can-play="canPlayEJS"
        />

        <RTabNav v-model="tab" :items="tabs" class="r-v2-det__tabs" />

        <div class="r-v2-det__panel">
          <OverviewTab
            v-if="tab === 'overview'"
            :rom="currentRom"
            :summary="currentRom.summary ?? null"
            :sections="overviewSections"
            :player-count="playerCount"
            :user-collections="userCollections"
            :hltb="currentRom.hltb_metadata"
            :last-played="lastPlayed"
            :screenshots="currentRom.merged_screenshots ?? []"
            :expansions="expansions"
            :dlcs="dlcs"
            :remakes="remakes"
            :remasters="remasters"
            :similar-games="similarGames"
          />
          <MediaTab v-if="tab === 'media'" :rom="currentRom" />
          <NotesTab v-if="tab === 'notes'" :rom="currentRom" />
          <AchievementsTab
            v-if="tab === 'achievements'"
            :metadata="raMetadata"
            :earned-achievement-ids="earnedAchievementIds"
          />
          <SaveDataTab v-if="tab === 'save-data'" :rom="currentRom" />
          <MetadataTab v-if="tab === 'metadata'" :rom="currentRom" />
        </div>
      </div>
    </div>
  </section>

  <section v-else class="r-v2-det__empty">
    <p>Loading ROM…</p>
  </section>
</template>

<style scoped>
.r-v2-det {
  position: relative;
  /* Fits the main viewport exactly (under the fixed AppNav) so the
     cover + header + tabs stay static and only the tab panel scrolls
     internally. No overflow at the view level → no document scroll
     on details. */
  height: calc(100vh - var(--r-nav-h));
  display: flex;
  flex-direction: column;
  padding-top: 20px;
}

.r-v2-det__topbar {
  position: relative;
  z-index: 2;
  padding: 20px var(--r-row-pad) 0;
}

.r-v2-det__body {
  position: relative;
  z-index: 2;
  flex: 1;
  display: flex;
  /* `stretch` (default) so the info column fills the body height —
     needed so the inner panel can use `flex: 1` + `min-height: 0` to
     scroll. The cover keeps its natural height via `align-self:
     flex-start` declared on CoverColumn itself. */
  align-items: stretch;
  padding: 0 var(--r-row-pad) 32px;
  gap: 52px;
  min-height: 0;
  /* Cap the canvas so the cover + info column stay readable on
     ultrawide displays. Below the cap this is a no-op. */
  max-width: var(--r-page-max-w);
  width: 100%;
  margin-left: auto;
  margin-right: auto;
}

.r-v2-det__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  /* Required for the inner panel's `flex: 1` + `overflow-y: auto`
     to compute against this container's height (otherwise flex
     children can't shrink below their intrinsic content size). */
  min-height: 0;
}

.r-v2-det__tabs {
  margin: 14px 0 16px;
}

.r-v2-det__panel {
  /* Sole scroll context within the details view: cover, header and
     tab nav stay frozen, only the active tab's content scrolls. */
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
  margin-top: 10px;
  padding-right: 6px;
}
.r-v2-det__panel::-webkit-scrollbar {
  width: 4px;
}
.r-v2-det__panel::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 2px;
}

.r-v2-det__empty {
  flex: 1;
  display: grid;
  place-items: center;
  color: var(--r-color-fg-muted);
  font-size: 13px;
}

html[data-bp~="xs"] .r-v2-det__body {
  padding: 12px 14px 0;
  gap: 14px;
  align-items: flex-start;
}
</style>
