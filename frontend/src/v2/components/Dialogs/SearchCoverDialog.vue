<script setup lang="ts">
// SearchCoverDialog: global cover-search dialog. Listens for the
// `showSearchCoverDialog` emitter event (term + optional platformId
// + optional source rom), queries `sgdbApi.searchCover` for the
// SteamGridDB and Steam grids, and, when a `rom` is provided, also
// calls `romApi.searchRom` to surface the cover URLs that IGDB,
// MobyGames, Screenscraper, Flashpoint, Launchbox and Libretro have
// for this game. Picking any cover fires `updateUrlCover` with the
// full resolution URL; consumers (EditRom, CollectionSettingsDrawer)
// own the actual save.
//
// Why fold the provider covers in here: previously the user had to
// open the manual-match flow just to swap an IGDB cover, even though
// the rom already had `igdb_id` set. The shared `/search/roms`
// endpoint returns the per-provider URLs in one call, so a parallel
// fetch keeps the surface to a single dialog.
//
// Collection-cover edits don't pass a `rom`, so they hit the cover grids
// only (collections don't have provider IDs in the same way).
import type { Emitter } from "mitt";
import { computed, inject, nextTick, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type {
  CoverResource,
  SearchCoverSchema,
  SearchRomSchema,
} from "@/__generated__";
import romApi from "@/services/api/rom";
import sgdbApi from "@/services/api/sgdb";
import storeHeartbeat from "@/stores/heartbeat";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import MatchRomProviderFilter from "@/v2/components/MatchRom/MatchRomProviderFilter.vue";
import {
  getMatchSources,
  sourceLogo,
  type MatchedSource,
  type SourceName,
} from "@/v2/components/MatchRom/types";
import {
  useCoverFilters,
  type CoverProvider,
  type SortMode,
} from "@/v2/composables/useCoverFilters";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RSelect from "@/v2/lib/forms/RSelect/RSelect.vue";
import RSwitch from "@/v2/lib/forms/RSwitch/RSwitch.vue";
import RTextField from "@/v2/lib/forms/RTextField/RTextField.vue";
import RMenu from "@/v2/lib/menus/RMenu/RMenu.vue";
import RMenuItem from "@/v2/lib/menus/RMenuItem/RMenuItem.vue";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import RDivider from "@/v2/lib/primitives/RDivider/RDivider.vue";
import REmptyState from "@/v2/lib/primitives/REmptyState/REmptyState.vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RSpinner from "@/v2/lib/primitives/RSpinner/RSpinner.vue";
import RTag from "@/v2/lib/primitives/RTag/RTag.vue";
import RCollapsible from "@/v2/lib/structural/RCollapsible/RCollapsible.vue";
import RExpandTransition from "@/v2/lib/structural/RExpandTransition/RExpandTransition.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const heartbeat = storeHeartbeat();

const show = ref(false);
const searching = ref(false);
const searchText = ref("");
const covers = ref<SearchCoverSchema[]>([]);
// Source rom for the in-flight search — drives the optional
// `/search/roms` companion call. Reset on close so a follow-up open
// without a `rom` payload (e.g. from CollectionSettingsDrawer) doesn't
// inherit a stale rom.
const sourceRom = ref<SimpleRom | null>(null);
const providerCovers = ref<MatchedSource[]>([]);

// The grid providers, keyed as the backend tags each result. The chips
// mirror the match dialog's filter row: disabled when the backend has no
// key for the provider, toggled off by the user to hide its covers.
const gridProviders = computed<
  { key: CoverProvider; name: SourceName; enabled: boolean }[]
>(() => [
  {
    key: "sgdb",
    name: "SteamGridDB",
    enabled: !!heartbeat.value.METADATA_SOURCES?.STEAMGRIDDB_API_ENABLED,
  },
  {
    key: "steam",
    name: "Steam",
    enabled: !!heartbeat.value.METADATA_SOURCES?.STEAM_API_ENABLED,
  },
]);
function gridProviderLogo(key: CoverProvider): string {
  const provider = gridProviders.value.find((p) => p.key === key);
  return provider ? sourceLogo(provider.name) : "";
}

// Client-side filtering + sorting over the two fetched lists. The
// backend returns every content variant (NSFW / humor / epilepsy) with
// its per-cover metadata in one call, so the controls just narrow the
// already-loaded results — no re-fetch.
const {
  coverType,
  resolutionFilter,
  styleFilter,
  uploaderFilter,
  uploaderSearch,
  showNsfw,
  showHumor,
  showEpilepsy,
  sortMode,
  activeProviders,
  toggleProvider,
  resetFilters,
  activeFilterCount,
  coverTypeItems,
  resolutionItems,
  resolutionValues,
  styleItems,
  styleValues,
  uploaderItems,
  uploaderValues,
  filteredCovers,
  visibleProviderCovers,
  hasSgdbCovers,
  showProviderCovers,
  hasRawResults,
  hasResults,
} = useCoverFilters(covers, providerCovers);

const filtersOpen = ref(false);
const filtersPanel = ref<HTMLElement | null>(null);

// The panel opens at the top of the scrolling body, which may be scrolled
// down to the covers, so bring it into view.
async function toggleFilters() {
  filtersOpen.value = !filtersOpen.value;
  if (!filtersOpen.value) return;
  await nextTick();
  filtersPanel.value?.scrollIntoView({ block: "nearest" });
}

const sortItems = computed<{ id: SortMode; label: string; icon: string }[]>(
  () => [
    {
      id: "relevance",
      label: t("rom.cover-sort-relevance"),
      icon: "mdi-target",
    },
    {
      id: "votes",
      label: t("rom.cover-sort-votes"),
      icon: "mdi-thumb-up-outline",
    },
  ],
);
const sortLabel = computed(
  () => sortItems.value.find((item) => item.id === sortMode.value)?.label,
);

// SGDB animated covers ship their `thumb` as a `.webm` clip — an `<img>`
// element can't render those (broken-image icon). Detect by type or
// extension and swap to a `<video>` for those resources so the preview
// actually plays.
function isAnimated(resource: CoverResource): boolean {
  return (
    resource.type === "animated" || /\.(webm|mp4)(\?|$)/i.test(resource.thumb)
  );
}

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
  filtersOpen.value = false;
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
  const term = searchText.value.trim();
  const source = sourceRom.value;
  try {
    // Fire the grid search + (optional) provider lookup in parallel:
    // neither depends on the other and they both populate independent
    // sections of the same dialog. `allSettled` so a provider-side
    // failure doesn't take down the grid and vice versa.
    const [gridResult, providersResult] = await Promise.allSettled([
      sgdbApi.searchCover({ searchTerm: term }),
      source
        ? romApi.searchRom({
            romId: source.id,
            searchTerm: term,
            searchBy: "name",
          })
        : Promise.resolve(null),
    ]);

    if (gridResult.status === "fulfilled") {
      covers.value = gridResult.value.data;
    } else {
      const e = gridResult.reason as {
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
      // Drop a grid provider from the providers row only when its full
      // result set is in the grid below; listing it twice is noise, but
      // a grid that came back empty (a timed-out CDN probe, no artwork
      // on the store page) must not hide the one cover the match found.
      const inGrid = new Set(
        covers.value
          .filter((game) => game.resources.length > 0)
          .map((game) => game.provider),
      );
      const shownInGrid = gridProviders.value
        .filter((provider) => inGrid.has(provider.key))
        .map((provider) => provider.name);
      providerCovers.value = best
        ? getMatchSources(best).filter((s) => !shownInGrid.includes(s.name))
        : [];
    }
  } finally {
    searching.value = false;
  }
}

// SGDB serves a thumb resource and a full-resolution one; substituting
// "thumb" → "grid" in the URL is how v1 derived the full image. We
// keep the same swap so consumers receive the high-res URL. Steam
// serves one URL per asset, handed off as is.
function pickCover(url: string, provider: CoverProvider) {
  emitter?.emit(
    "updateUrlCover",
    provider === "sgdb" ? url.replace("thumb", "grid") : url,
  );
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
    compact-body
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.search-cover") }}</span>
    </template>

    <template #toolbar>
      <div class="r-v2-sgdb__toolbar">
        <div class="r-v2-sgdb__providers">
          <MatchRomProviderFilter
            v-for="provider in gridProviders"
            :key="provider.key"
            :name="provider.name"
            :label="provider.name"
            :logo="sourceLogo(provider.name)"
            :enabled="provider.enabled"
            :active="activeProviders[provider.key]"
            @toggle="toggleProvider(provider.key)"
          />
        </div>

        <div class="r-v2-sgdb__search-row">
          <RTextField
            v-model="searchText"
            :placeholder="t('common.search')"
            density="comfortable"
            prefix-label="inline"
            clearable
            hide-details
            @keyup.enter="doSearch"
          >
            <template #prefix-label>
              <RIcon icon="mdi-magnify" size="14" />
            </template>
          </RTextField>
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-magnify"
            :disabled="!searchText.trim() || searching"
            @click="doSearch"
          >
            {{ t("common.search") }}
          </RBtn>
        </div>

        <template v-if="hasRawResults">
          <RDivider />

          <div class="r-v2-sgdb__actions">
            <RBtn
              variant="outlined"
              surface
              size="small"
              prepend-icon="mdi-filter-variant"
              class="r-v2-sgdb__action"
              :aria-expanded="filtersOpen"
              aria-controls="r-v2-sgdb-filters"
              @click="toggleFilters"
            >
              {{ t("gallery.filters") }}
              <RTag v-if="activeFilterCount > 0" tone="brand" size="x-small">
                {{ activeFilterCount }}
              </RTag>
              <template #append>
                <RIcon
                  icon="mdi-chevron-down"
                  size="16"
                  class="r-chevron-toggle"
                />
              </template>
            </RBtn>

            <RMenu v-if="hasSgdbCovers" location="bottom end" :offset="6">
              <template #activator="{ props: activatorProps }">
                <RBtn
                  v-bind="activatorProps"
                  variant="outlined"
                  surface
                  size="small"
                  prepend-icon="mdi-sort-descending"
                  class="r-v2-sgdb__action"
                >
                  {{ sortLabel }}
                  <template #append>
                    <RIcon
                      icon="mdi-menu-down"
                      size="16"
                      class="r-chevron-toggle"
                    />
                  </template>
                </RBtn>
              </template>
              <RMenuItem
                v-for="item in sortItems"
                :key="item.id"
                :label="item.label"
                :icon="item.icon"
                :variant="sortMode === item.id ? 'active' : 'default'"
                @click="sortMode = item.id"
              />
            </RMenu>
          </div>
        </template>
      </div>
    </template>

    <template #content>
      <RExpandTransition>
        <div
          v-show="filtersOpen && hasRawResults"
          id="r-v2-sgdb-filters"
          ref="filtersPanel"
          class="r-v2-sgdb__advanced"
        >
          <div class="r-v2-sgdb__advanced-panel">
            <div class="r-v2-sgdb__filters">
              <RSelect
                v-model="coverType"
                :items="coverTypeItems"
                density="comfortable"
                hide-details
                class="r-v2-sgdb__filter"
                :aria-label="t('rom.cover-type-all')"
              />
              <template v-if="hasSgdbCovers">
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
              </template>
            </div>

            <div v-if="hasSgdbCovers" class="r-v2-sgdb__content-toggles">
              <RSwitch
                v-model="showNsfw"
                :label="t('rom.cover-content-nsfw')"
              />
              <RSwitch
                v-model="showHumor"
                :label="t('rom.cover-content-humor')"
              />
              <RSwitch
                v-model="showEpilepsy"
                :label="t('rom.cover-content-epilepsy')"
              />
            </div>
          </div>
        </div>
      </RExpandTransition>

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
            :title="t('rom.metadata-providers')"
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
            :key="`${game.provider}-${game.name}`"
            :title="game.name"
            default-open
          >
            <div class="r-v2-sgdb__grid">
              <button
                v-for="resource in game.resources"
                :key="resource.url"
                type="button"
                class="r-v2-sgdb__cover"
                @click="pickCover(resource.url, game.provider)"
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
                <span class="r-v2-sgdb__cover-provider">
                  <img
                    :src="gridProviderLogo(game.provider)"
                    :alt="game.provider"
                    class="r-v2-sgdb__cover-provider-logo"
                  />
                </span>
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
/* Same rhythm as the match dialog's toolbar. */
.r-v2-sgdb__toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.r-v2-sgdb__providers {
  display: flex;
  align-items: center;
  gap: 8px;
}

.r-v2-sgdb__search-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: stretch;
}
.r-v2-sgdb__search-row > * {
  min-width: 0;
}

.r-v2-sgdb__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.r-v2-sgdb__advanced {
  flex-shrink: 0;
  scroll-margin-top: var(--r-dialog-inset);
}
/* Same surface as the cover blocks below it. */
.r-v2-sgdb__advanced-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

/* The selects split the full row evenly, wrapping on narrow dialogs so
   none is squeezed below a readable width. */
.r-v2-sgdb__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.r-v2-sgdb__filter {
  flex: 1 1 0;
  min-width: 130px;
}

.r-v2-sgdb__content-toggles {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

html[data-bp~="xs"] .r-v2-sgdb__search-row {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-sgdb__action {
  flex: 1 1 0;
}
html[data-bp~="xs"] .r-v2-sgdb__content-toggles {
  justify-content: center;
}

.r-v2-sgdb__body {
  min-height: 280px;
}

.r-v2-sgdb__loading {
  display: grid;
  place-items: center;
  min-height: 280px;
}

/* Chrome can leave the scrolling body's own bottom padding out of the scroll
   area, so the stack carries it to keep the last block off the edge. */
.r-v2-sgdb__results {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: var(--r-dialog-inset);
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
