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
import { onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import type { IGDBRelatedGame } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import { toBrowserLocale } from "@/utils";
import AchievementsTab from "@/v2/components/GameDetails/AchievementsTab.vue";
import CoverColumn from "@/v2/components/GameDetails/CoverColumn.vue";
import FilesTab from "@/v2/components/GameDetails/FilesTab/FilesTab.vue";
import GameHeader from "@/v2/components/GameDetails/GameHeader.vue";
import type { InfoGridSection } from "@/v2/components/GameDetails/InfoGrid.vue";
import MediaTab from "@/v2/components/GameDetails/MediaTab.vue";
import MetadataTab from "@/v2/components/GameDetails/MetadataTab.vue";
import NotesTab from "@/v2/components/GameDetails/NotesTab.vue";
import OverviewTab from "@/v2/components/GameDetails/OverviewTab.vue";
import PatcherTab from "@/v2/components/GameDetails/PatcherTab.vue";
import SaveDataTab from "@/v2/components/GameDetails/SaveDataTab.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useRightStickScroll } from "@/v2/composables/useRightStickScroll";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import { isRomVerified } from "@/v2/utils/romVerification";

const route = useRoute();
const router = useRouter();
const romsStore = storeRoms();
const authStore = storeAuth();
const { currentRom } = storeToRefs(romsStore);
const { toWebp } = useWebpSupport();
const { locale, t } = useI18n();

const setBgArt = useBackgroundArt();

// Param-change navigation guard — the route's `beforeEnter` in
// `plugins/router.ts` only fires on initial entry; navigating between
// `/rom/123` and `/rom/456` reuses this component, so currentRom
// would stay stale (e.g. clicking an "Owned" related game card
// wouldn't refresh the view). Mirror the beforeEnter logic here for
// param updates, then scroll the panel back to the top so the new
// ROM's overview doesn't start halfway down where the user clicked.
const panelEl = ref<HTMLElement | null>(null);

// Right stick scrolls the tab panel — D-pad / A move focus across the
// action ribbon, right stick scrolls long tabs (Overview, Achievements)
// without needing to leave the ribbon focus.
useRightStickScroll(panelEl);

onBeforeRouteUpdate(async (to) => {
  const nextId = parseInt(to.params.rom as string);
  if (Number.isNaN(nextId)) return;
  const sameRom = romsStore.currentRom?.id === nextId;
  if (!sameRom) {
    try {
      const { data } = await romApi.getRom({ romId: nextId });
      romsStore.setCurrentRom(data);
    } catch (error) {
      console.error(error);
    }
  }
  // Reset the per-view scroll on every navigation (even if the
  // currentRom hasn't changed — e.g. re-entering the same ROM from
  // its own page): the panel is the sole scroll context here.
  panelEl.value?.scrollTo({ top: 0, behavior: "smooth" });
});

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

const verified = computed(() =>
  currentRom.value ? isRomVerified(currentRom.value) : false,
);

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
  { label: t("rom.genres"), items: genres.value },
  { label: t("rom.companies"), items: companies.value },
  { label: t("rom.franchises"), items: franchises.value },
  { label: t("rom.collections"), items: collections.value },
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
// IGDB ships up to ~10 similar games per title; rendering all of them
// would dominate the overview and push HLTB/Achievements below the
// fold. Cap to keep the section to ~2 rows of cards at typical widths.
const SIMILAR_GAMES_MAX = 6;
const similarGames = computed<IGDBRelatedGame[]>(() =>
  (igdb.value?.similar_games ?? []).slice(0, SIMILAR_GAMES_MAX),
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

const filesCount = computed(() => currentRom.value?.files?.length ?? 0);

// The patcher tab is always available: a base game file can be patched with
// one of the ROM's bundled patch files or with a patch uploaded from disk, so
// users don't have to store patches in the library until they need them.
const tabs = computed<RTabNavItem[]>(() => [
  { id: "overview", label: t("rom.tab-overview") },
  { id: "files", label: t("rom.tab-files"), badge: filesCount.value },
  { id: "patcher", label: t("common.patcher") },
  { id: "media", label: t("rom.media") },
  { id: "notes", label: t("rom.tab-notes") },
  {
    id: "achievements",
    label: t("rom.tab-achievements"),
    badge: `${achievementsEarned.value}/${achievementsTotal.value}`,
  },
  {
    id: "save-data",
    label: t("rom.save-data"),
    badge: saveDataCount.value,
  },
  { id: "metadata", label: t("rom.metadata") },
]);
</script>

<template>
  <section v-if="currentRom" class="r-v2-det">
    <div class="r-v2-det__body">
      <CoverColumn :rom="currentRom" :alt="title" />

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
        />

        <RTabNav v-model="tab" :items="tabs" class="r-v2-det__tabs" />

        <div ref="panelEl" class="r-v2-det__panel">
          <OverviewTab
            v-if="tab === 'overview'"
            :rom="currentRom"
            :summary="currentRom.summary ?? null"
            :sections="overviewSections"
            :player-count="playerCount"
            :user-collections="userCollections"
            :hltb="currentRom.hltb_metadata"
            :last-played="lastPlayed"
            :revision="currentRom.revision ?? null"
            :screenshots="currentRom.merged_screenshots ?? []"
            :expansions="expansions"
            :dlcs="dlcs"
            :remakes="remakes"
            :remasters="remasters"
            :similar-games="similarGames"
          />
          <FilesTab v-if="tab === 'files'" :rom="currentRom" />
          <PatcherTab v-if="tab === 'patcher'" :rom="currentRom" />
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
    <p>{{ t("rom.loading-rom") }}</p>
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
     tab nav stay frozen, only the active tab's content scrolls.
     `position: relative` lets self-contained tabs (FilesTab) anchor
     an absolutely-positioned root to this panel's visible viewport
     when they want internal scroll instead of the panel's scroll. */
  position: relative;
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

/* Mobile / small tablet: stack the cover above the info column, and — unlike
   desktop — let the WHOLE view scroll as one document instead of freezing the
   cover/header/tabs and scrolling only the panel. A phone has no room to keep
   half the screen static; the desktop "fixed cover + inner panel scroll"
   layout makes no sense here. So the section grows with its content and the
   AppLayout document scroll takes over (its bottom-nav padding clears the last
   content). Every fixed-height / internal-scroll rule is unwound below. */
html[data-bp~="sm-and-down"] .r-v2-det {
  padding-top: 8px;
  height: auto;
}
html[data-bp~="sm-and-down"] .r-v2-det__body {
  flex-direction: column;
  align-items: stretch;
  gap: 14px;
  padding: 8px var(--r-row-pad) 16px;
  flex: none;
  min-height: 0;
}
html[data-bp~="sm-and-down"] .r-v2-det__info {
  flex: none;
  min-height: 0;
}
html[data-bp~="sm-and-down"] .r-v2-det__panel {
  flex: none;
  min-height: 0;
  height: auto;
  overflow: visible;
  padding-right: 0;
}
html[data-bp~="sm-and-down"] .r-v2-det__tabs {
  margin: 28px 0 12px;
}
</style>
