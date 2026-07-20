<script setup lang="ts">
// SearchCoverDialog — global cover-search dialog. Listens for the
// `showSearchCoverDialog` emitter event (term + optional platformId
// + optional source rom), queries `sgdbApi.searchCover` for SGDB
// thumbs, and — when a `rom` is provided — also calls
// `romApi.searchRom` to surface the cover URLs that IGDB, MobyGames,
// Screenscraper, Flashpoint, Launchbox and Libretro have for this
// game. Picking any cover fires `updateUrlCover` with the full
// resolution URL; consumers (EditRom, CollectionSettingsDrawer) own
// the actual save.
//
// Why fold the provider covers in here: previously the user had to
// open the manual-match flow just to swap an IGDB cover, even though
// the rom already had `igdb_id` set. The shared `/search/roms`
// endpoint returns the per-provider URLs in one call, so a parallel
// fetch keeps the surface to a single dialog.
//
// Collection-cover edits don't pass a `rom` — they hit SGDB only
// (collections don't have provider IDs in the same way).
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type {
  SearchCoverSchema,
  SearchRomSchema,
  SGDBResource,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import sgdbApi from "@/services/api/sgdb";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import {
  getMatchSources,
  type MatchedSource,
} from "@/v2/components/MatchRom/types";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RSelect from "@/v2/lib/forms/RSelect/RSelect.vue";
import RSwitch from "@/v2/lib/forms/RSwitch/RSwitch.vue";
import RTextField from "@/v2/lib/forms/RTextField/RTextField.vue";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import REmptyState from "@/v2/lib/primitives/REmptyState/REmptyState.vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RSpinner from "@/v2/lib/primitives/RSpinner/RSpinner.vue";
import RCollapsible from "@/v2/lib/structural/RCollapsible/RCollapsible.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

type CoverType = "all" | "static" | "animated";

const show = ref(false);
const searching = ref(false);
const searchText = ref("");
const coverType = ref<CoverType>("all");
const covers = ref<SearchCoverSchema[]>([]);
// Source rom for the in-flight search — drives the optional
// `/search/roms` companion call. Reset on close so a follow-up open
// without a `rom` payload (e.g. from CollectionSettingsDrawer) doesn't
// inherit a stale rom.
const sourceRom = ref<SimpleRom | null>(null);
const providerCovers = ref<MatchedSource[]>([]);

// Client-side filters over the fetched result set. They never re-hit the
// API — the backend returns every content variant (NSFW / humor /
// epilepsy) with its per-cover metadata, so flipping a filter just
// narrows the already-loaded list. Option lists below are built from the
// raw results, so filtering never removes an option the user might want.
type SortMode = "relevance" | "votes";
const sourceFilter = ref("all"); // "all" | "sgdb" | provider name
const resolutionFilter = ref("all");
const styleFilter = ref("all");
const uploaderFilter = ref("all");
const uploaderSearch = ref("");
const showNsfw = ref(false);
const showHumor = ref(true);
const showEpilepsy = ref(true);
const sortMode = ref<SortMode>("relevance");

function resetFilters() {
  coverType.value = "all";
  sourceFilter.value = "all";
  resolutionFilter.value = "all";
  styleFilter.value = "all";
  uploaderFilter.value = "all";
  uploaderSearch.value = "";
  showNsfw.value = false;
  showHumor.value = true;
  showEpilepsy.value = true;
  sortMode.value = "relevance";
}

// SGDB serves styles as raw slugs; map the known set to readable labels
// and fall back to the slug for anything new SGDB adds later.
const STYLE_LABEL_KEYS: Record<string, string> = {
  alternate: "rom.cover-style-alternate",
  blurred: "rom.cover-style-blurred",
  white_logo: "rom.cover-style-white-logo",
  material: "rom.cover-style-material",
  no_logo: "rom.cover-style-no-logo",
};
function styleLabel(style: string): string {
  const key = STYLE_LABEL_KEYS[style];
  return key ? t(key) : style;
}

const coverTypeItems = computed(() => [
  { title: t("rom.cover-type-all"), value: "all" },
  { title: t("rom.cover-type-static"), value: "static" },
  { title: t("rom.cover-type-animated"), value: "animated" },
]);

const sortItems = computed(() => [
  { title: t("rom.cover-sort-relevance"), value: "relevance" },
  { title: t("rom.cover-sort-votes"), value: "votes" },
]);

// Every SGDB resource across all matched games, used to build the
// dynamic option lists (resolution / style / uploader) from what the
// search actually returned.
const allResources = computed(() => covers.value.flatMap((g) => g.resources));

const resolutionValues = computed(() => {
  const set = new Set<string>();
  for (const r of allResources.value) {
    if (r.width > 0 && r.height > 0) set.add(`${r.width}x${r.height}`);
  }
  // Largest area first — the highest-res covers are what users usually want.
  return [...set].sort((a, b) => {
    const [aw, ah] = a.split("x").map(Number);
    const [bw, bh] = b.split("x").map(Number);
    return bw * bh - aw * ah || bw - aw;
  });
});
const resolutionItems = computed(() => [
  { title: t("rom.cover-filter-resolution-all"), value: "all" },
  ...resolutionValues.value.map((v) => ({
    title: v.replace("x", "×"),
    value: v,
  })),
]);

const styleValues = computed(() => {
  const set = new Set<string>();
  for (const r of allResources.value) if (r.style) set.add(r.style);
  return [...set].sort();
});
const styleItems = computed(() => [
  { title: t("rom.cover-filter-style-all"), value: "all" },
  ...styleValues.value.map((v) => ({ title: styleLabel(v), value: v })),
]);

const uploaderValues = computed(() => {
  const set = new Set<string>();
  for (const r of allResources.value) if (r.author) set.add(r.author);
  return [...set].sort((a, b) => a.localeCompare(b));
});
const uploaderItems = computed(() => [
  { title: t("rom.cover-filter-uploader-all"), value: "all" },
  ...uploaderValues.value.map((v) => ({ title: v, value: v })),
]);

// Source select only makes sense once provider covers are in play (the
// dialog was opened from a rom). Options: All, SteamGridDB, then one per
// provider that returned a cover.
const sourceItems = computed(() => {
  const items = [{ title: t("rom.cover-filter-source-all"), value: "all" }];
  if (allResources.value.length > 0) {
    items.push({ title: "SteamGridDB", value: "sgdb" });
  }
  for (const s of providerCovers.value)
    items.push({ title: s.name, value: s.name });
  return items;
});

// Does a single SGDB resource pass all active filters?
function matchesFilters(r: SGDBResource): boolean {
  if (coverType.value !== "all" && r.type !== coverType.value) return false;
  if (
    resolutionFilter.value !== "all" &&
    `${r.width}x${r.height}` !== resolutionFilter.value
  )
    return false;
  if (styleFilter.value !== "all" && r.style !== styleFilter.value)
    return false;
  if (uploaderFilter.value !== "all" && r.author !== uploaderFilter.value)
    return false;
  // Content flags are opt-in: a flagged cover shows only when its toggle is on.
  if (r.nsfw && !showNsfw.value) return false;
  if (r.humor && !showHumor.value) return false;
  if (r.epilepsy && !showEpilepsy.value) return false;
  return true;
}

// SGDB results render unless the source filter isolates a single provider.
const showSgdb = computed(
  () => sourceFilter.value === "all" || sourceFilter.value === "sgdb",
);

// Filter (and optionally re-sort by votes) the fetched SGDB list without
// re-hitting the API. SGDB sometimes returns a game entry with an empty
// `resources` array — or one emptied by the active filters — so we drop
// those so the accordion doesn't render an empty section.
const filteredCovers = computed<SearchCoverSchema[]>(() => {
  if (!showSgdb.value) return [];
  return covers.value
    .map((game) => {
      const resources = game.resources.filter(matchesFilters);
      if (sortMode.value === "votes") {
        resources.sort((a, b) => b.score - a.score);
      }
      return { ...game, resources };
    })
    .filter((g) => g.resources.length > 0);
});

// SGDB animated covers ship their `thumb` as a `.webm` clip — an `<img>`
// element can't render those (broken-image icon). Detect by type or
// extension and swap to a `<video>` for those resources so the preview
// actually plays.
function isAnimated(resource: SGDBResource): boolean {
  return (
    resource.type === "animated" || /\.(webm|mp4)(\?|$)/i.test(resource.thumb)
  );
}

const hasSgdbCovers = computed(() => allResources.value.length > 0);
const hasProviderCovers = computed(() => providerCovers.value.length > 0);
// Provider covers (IGDB / Moby / SS / …) are static artwork only — they
// don't carry an animated variant, so hide them when filtering to
// "animated". The source filter can also isolate a single provider.
const visibleProviderCovers = computed<MatchedSource[]>(() => {
  if (coverType.value === "animated") return [];
  if (sourceFilter.value === "sgdb") return [];
  if (sourceFilter.value === "all") return providerCovers.value;
  return providerCovers.value.filter((s) => s.name === sourceFilter.value);
});

const hasSgdbResults = computed(() => filteredCovers.value.length > 0);
const showProviderCovers = computed(
  () => visibleProviderCovers.value.length > 0,
);
// Raw results present (pre-filter) — drives whether the filter bar shows,
// so filtering everything out never hides the controls needed to undo it.
const hasRawResults = computed(
  () => hasSgdbCovers.value || hasProviderCovers.value,
);
const hasResults = computed(
  () => hasSgdbResults.value || showProviderCovers.value,
);
// A search ran and the server returned nothing at all.
const showNoServerResults = computed(
  () => !searching.value && searchText.value.length > 0 && !hasRawResults.value,
);
// The server returned covers but the active filters exclude them all.
const showNoFilterMatch = computed(
  () => !searching.value && hasRawResults.value && !hasResults.value,
);

function openHandler({
  term,
  rom,
}: {
  term: string;
  platformId?: number;
  rom?: SimpleRom;
}) {
  searchText.value = term;
  covers.value = [];
  providerCovers.value = [];
  resetFilters();
  sourceRom.value = rom ?? null;
  show.value = true;
  if (searchText.value) doSearch();
}
emitter?.on("showSearchCoverDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showSearchCoverDialog", openHandler));

// Score a `/search/roms` result by how many of its provider IDs match
// the source rom's IDs. The highest-scoring result is the same game
// the user already has identified, so its per-provider URL covers can
// be surfaced as "this is what IGDB/Moby/… have for this rom".
function scoreAgainstSourceRom(
  result: SearchRomSchema,
  source: SimpleRom,
): number {
  let score = 0;
  if (source.igdb_id && result.igdb_id === source.igdb_id) score += 1;
  if (source.moby_id && result.moby_id === source.moby_id) score += 1;
  if (source.ss_id && result.ss_id === source.ss_id) score += 1;
  if (source.flashpoint_id && result.flashpoint_id === source.flashpoint_id)
    score += 1;
  if (source.launchbox_id && result.launchbox_id === source.launchbox_id)
    score += 1;
  return score;
}

async function doSearch() {
  if (searching.value || !searchText.value.trim()) return;
  searching.value = true;
  covers.value = [];
  providerCovers.value = [];
  resetFilters();
  const term = searchText.value.trim();
  const source = sourceRom.value;
  try {
    // Fire SGDB + (optional) provider lookup in parallel — neither
    // depends on the other and they both populate independent
    // sections of the same dialog. `allSettled` so a provider-side
    // failure doesn't take down the SGDB grid and vice versa.
    const [sgdbResult, providersResult] = await Promise.allSettled([
      sgdbApi.searchCover({ searchTerm: term }),
      source
        ? romApi.searchRom({
            romId: source.id,
            searchTerm: term,
            searchBy: "name",
          })
        : Promise.resolve(null),
    ]);

    if (sgdbResult.status === "fulfilled") {
      covers.value = sgdbResult.value.data;
    } else {
      const e = sgdbResult.reason as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      snackbar.error(
        t("rom.cover-search-failed", {
          error:
            e?.response?.data?.detail ||
            e?.message ||
            t("common.unknown-error"),
        }),
        { icon: "mdi-close-circle" },
      );
    }

    if (
      source &&
      providersResult.status === "fulfilled" &&
      providersResult.value
    ) {
      const results = providersResult.value.data;
      // Prefer the result that shares the most IDs with our rom (the
      // same identified game). When no result matches by ID — e.g. an
      // unidentified rom — fall back to the first one so the user
      // still gets something. `0` score with a populated `results`
      // array still picks `results[0]`.
      const best = [...results]
        .sort(
          (a, b) =>
            scoreAgainstSourceRom(b, source) - scoreAgainstSourceRom(a, source),
        )
        .at(0);
      // Drop SteamGridDB from the providers row — the dialog already
      // surfaces the full SGDB cover grid below, listing it twice
      // (once as a single tile, once as the full result set) is just
      // noise.
      providerCovers.value = best
        ? getMatchSources(best).filter((s) => s.name !== "SteamGridDB")
        : [];
    }
  } finally {
    searching.value = false;
  }
}

// SGDB serves a thumb resource and a full-resolution one; substituting
// "thumb" → "grid" in the URL is how v1 derived the full image. We
// keep the same swap so consumers receive the high-res URL.
function pickCover(url: string) {
  emitter?.emit("updateUrlCover", url.replace("thumb", "grid"));
  closeDialog();
}

// Provider covers (IGDB / Moby / SS / …) already come at full
// resolution from `/search/roms`, so no thumb-→-grid swap — just hand
// the URL off to the consumer.
function pickProviderCover(url: string) {
  emitter?.emit("updateUrlCover", url);
  closeDialog();
}

function closeDialog() {
  show.value = false;
  covers.value = [];
  providerCovers.value = [];
  sourceRom.value = null;
  searchText.value = "";
  resetFilters();
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-image-search-outline"
    :width="900"
    scroll-content
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.search-cover") }}</span>
    </template>

    <template #content>
      <div class="r-v2-sgdb__toolbar">
        <RTextField
          v-model="searchText"
          :placeholder="t('common.search')"
          density="comfortable"
          prefix-label="inline"
          clearable
          hide-details
          class="r-v2-sgdb__search"
          @keyup.enter="doSearch"
        >
          <template #prefix-label>
            <RIcon icon="mdi-magnify" size="16" />
          </template>
        </RTextField>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-magnify"
          :loading="searching"
          :disabled="!searchText.trim() || searching"
          @click="doSearch"
        >
          {{ t("common.search") }}
        </RBtn>
      </div>

      <!-- Filter bar — client-side only, built from the fetched results.
           Gated on `hasRawResults` (not the filtered list) so filtering
           everything out never hides the controls needed to undo it. -->
      <div v-if="hasRawResults" class="r-v2-sgdb__filters">
        <RSelect
          v-model="coverType"
          :items="coverTypeItems"
          density="comfortable"
          hide-details
          class="r-v2-sgdb__filter"
          :aria-label="t('rom.cover-type-all')"
        />
        <RSelect
          v-if="hasProviderCovers"
          v-model="sourceFilter"
          :items="sourceItems"
          density="comfortable"
          hide-details
          class="r-v2-sgdb__filter"
          :aria-label="t('rom.cover-filter-source-all')"
        />
        <template v-if="hasSgdbCovers && showSgdb">
          <RSelect
            v-if="resolutionValues.length > 1"
            v-model="resolutionFilter"
            :items="resolutionItems"
            density="comfortable"
            hide-details
            class="r-v2-sgdb__filter"
            :aria-label="t('rom.cover-filter-resolution-all')"
          />
          <RSelect
            v-if="styleValues.length > 1"
            v-model="styleFilter"
            :items="styleItems"
            density="comfortable"
            hide-details
            class="r-v2-sgdb__filter"
            :aria-label="t('rom.cover-filter-style-all')"
          />
          <RSelect
            v-if="uploaderValues.length > 1"
            v-model="uploaderFilter"
            v-model:search="uploaderSearch"
            :items="uploaderItems"
            density="comfortable"
            hide-details
            searchable
            :search-placeholder="t('common.search')"
            class="r-v2-sgdb__filter"
            :aria-label="t('rom.cover-filter-uploader-all')"
          />
          <RSelect
            v-model="sortMode"
            :items="sortItems"
            density="comfortable"
            hide-details
            class="r-v2-sgdb__filter"
            :aria-label="t('rom.cover-sort-relevance')"
          />
          <div class="r-v2-sgdb__toggles">
            <RSwitch v-model="showNsfw" :label="t('rom.cover-content-nsfw')" />
            <RSwitch
              v-model="showHumor"
              :label="t('rom.cover-content-humor')"
            />
            <RSwitch
              v-model="showEpilepsy"
              :label="t('rom.cover-content-epilepsy')"
            />
          </div>
        </template>
      </div>

      <div class="r-v2-sgdb__body">
        <div v-if="searching" class="r-v2-sgdb__loading">
          <RSpinner :size="36" />
        </div>

        <div v-else-if="hasResults" class="r-v2-sgdb__results">
          <!-- Provider covers — one card per metadata source that
               returned a URL for this rom. Renders only when the
               dialog was opened with a `rom` payload; the provider
               logo overlays the card so the user can read at a
               glance whose artwork they're picking. -->
          <RCollapsible
            v-if="showProviderCovers"
            :title="t('rom.providers-covers')"
            default-open
          >
            <div class="r-v2-sgdb__grid">
              <button
                v-for="src in visibleProviderCovers"
                :key="`${src.name}-${src.url_cover}`"
                type="button"
                class="r-v2-sgdb__cover"
                :title="src.name"
                :aria-label="src.name"
                @click="pickProviderCover(src.url_cover)"
              >
                <img
                  :src="src.url_cover"
                  :alt="src.name"
                  loading="lazy"
                  class="r-v2-sgdb__cover-img"
                />
                <span class="r-v2-sgdb__cover-provider">
                  <img
                    :src="src.logo_path"
                    :alt="src.name"
                    class="r-v2-sgdb__cover-provider-logo"
                  />
                </span>
              </button>
            </div>
          </RCollapsible>

          <RCollapsible
            v-for="game in filteredCovers"
            :key="game.name"
            :title="game.name"
            default-open
          >
            <div class="r-v2-sgdb__grid">
              <button
                v-for="resource in game.resources"
                :key="resource.url"
                type="button"
                class="r-v2-sgdb__cover"
                @click="pickCover(resource.url)"
              >
                <video
                  v-if="isAnimated(resource)"
                  :src="resource.thumb"
                  class="r-v2-sgdb__cover-img"
                  autoplay
                  loop
                  muted
                  playsinline
                />
                <img
                  v-else
                  :src="resource.thumb"
                  :alt="game.name"
                  loading="lazy"
                  class="r-v2-sgdb__cover-img"
                />
              </button>
            </div>
          </RCollapsible>
        </div>

        <REmptyState
          v-else-if="showNoFilterMatch"
          variant="boxed"
          icon="mdi-filter-remove-outline"
          :message="t('rom.no-covers-match-filters')"
        />

        <REmptyState
          v-else-if="showNoServerResults"
          variant="boxed"
          icon="mdi-emoticon-confused-outline"
          :message="t('rom.no-covers-found')"
        />

        <REmptyState
          v-else
          variant="boxed"
          icon="mdi-image-search-outline"
          :message="t('rom.search-cover-hint')"
        />
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-sgdb__toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}
.r-v2-sgdb__search {
  flex: 1 1 auto;
  min-width: 0;
}

/* Filter bar — wraps onto multiple rows on narrow dialogs so no control
   is ever clipped. Each select takes a comfortable fixed width; the
   content toggles group flows to the end. */
.r-v2-sgdb__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 14px;
}
.r-v2-sgdb__filter {
  flex: 0 1 160px;
  min-width: 130px;
}
.r-v2-sgdb__toggles {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.r-v2-sgdb__body {
  min-height: 280px;
}

.r-v2-sgdb__loading {
  display: grid;
  place-items: center;
  min-height: 280px;
}

/* Unified results stack — providers panel + per-game SGDB collapsibles
   share the same column with one consistent gap, so the top of the
   first SGDB collapsible sits the same distance from the providers
   panel as the gap between consecutive collapsibles below.
   `padding-bottom: 24px` matches the dialog body's horizontal padding
   (24px), giving the last collapsible the same breathing room against
   the dialog edge as the items have against the side walls. Chrome
   doesn't always include the flex parent's `padding-bottom` in the
   scroll area when the body uses `overflow-y: auto` with flex layout,
   so anchoring the spacer on the inner stack keeps it reliable. */
.r-v2-sgdb__results {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 24px;
}

/* Flow-pack of cover cards — each tile adopts its cover's natural aspect
   (fixed height, width follows the art), like the gallery cards, instead of
   a rigid uniform-width grid. */
.r-v2-sgdb__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 16px 16px;
}

.r-v2-sgdb__cover {
  appearance: none;
  position: relative;
  display: grid;
  place-items: center;
  /* Reserve roughly a 2:3 slot so tiles don't collapse before their image
     loads; the tile then grows to the cover's true width on load. */
  min-width: 120px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
  padding: 0;
  background: var(--r-color-bg-elevated);
  cursor: pointer;
  overflow: hidden;
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-sgdb__cover:hover {
  border-color: var(--r-color-brand-primary);
  transform: translateY(-2px);
}
.r-v2-sgdb__cover-img {
  display: block;
  /* Fixed height, natural width — the card takes the cover's true aspect,
     never cropped. `max-width` caps the rare ultra-wide cover to the tile so
     it letterboxes instead of overflowing past its rounded corners. */
  height: 180px;
  width: auto;
  max-width: 100%;
  object-fit: contain;
}

/* Provider logo overlay — top-right corner badge on the cover so the
   user sees at a glance which metadata source the artwork belongs to. */
.r-v2-sgdb__cover-provider {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-overlay-scrim-strong);
  border: 1px solid var(--r-color-overlay-border);
  padding: 2px;
}
.r-v2-sgdb__cover-provider-logo {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 3px;
}
</style>
