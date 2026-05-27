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

const coverTypeItems = computed(() => [
  { title: t("rom.cover-type-all"), value: "all" },
  { title: t("rom.cover-type-static"), value: "static" },
  { title: t("rom.cover-type-animated"), value: "animated" },
]);

// Filter happens after the search returns — splitting the source list
// and the visible list keeps the type-filter snappy without re-hitting
// the API for every flip. SGDB sometimes returns a game entry with an
// empty `resources` array (matched the title but no covers in the
// requested set); we drop those unconditionally so the accordion
// doesn't render an empty section.
const filteredCovers = computed<SearchCoverSchema[]>(() => {
  const base =
    coverType.value === "all"
      ? covers.value
      : covers.value.map((game) => ({
          ...game,
          resources: game.resources.filter((r) => r.type === coverType.value),
        }));
  return base.filter((g) => g.resources.length > 0);
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

const hasSgdbResults = computed(() => filteredCovers.value.length > 0);
const hasProviderCovers = computed(() => providerCovers.value.length > 0);
// Provider covers (IGDB / Moby / SS / …) are static artwork only — they
// don't carry an animated variant. Hide the panel when the user filters
// to "animated" so it doesn't leak through and break the filter promise.
const showProviderCovers = computed(
  () => hasProviderCovers.value && coverType.value !== "animated",
);
const hasResults = computed(
  () => hasSgdbResults.value || showProviderCovers.value,
);
const showEmpty = computed(
  () => !searching.value && searchText.value.length > 0 && !hasResults.value,
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
  coverType.value = "all";
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
        <RSelect
          v-model="coverType"
          :items="coverTypeItems"
          density="comfortable"
          hide-details
          class="r-v2-sgdb__type"
        />
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

      <div class="r-v2-sgdb__body">
        <div v-if="searching" class="r-v2-sgdb__loading">
          <RSpinner :size="36" />
        </div>

        <REmptyState
          v-else-if="showEmpty"
          variant="boxed"
          icon="mdi-emoticon-confused-outline"
          :message="t('rom.no-covers-found')"
        />

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
                v-for="src in providerCovers"
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
.r-v2-sgdb__type {
  flex: 0 0 140px;
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

.r-v2-sgdb__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  padding: 12px 16px 16px;
}

.r-v2-sgdb__cover {
  appearance: none;
  position: relative;
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
  width: 100%;
  aspect-ratio: 2 / 3;
  object-fit: cover;
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
