<script setup lang="ts">
// MatchRomDialog — manual metadata match flow. Users search any text via
// any provider, filter which providers to include, pick a result, pick a
// cover variant, and optionally rename the file to match.
//
// The v2 rewrite keeps the v1 `GameCard` + `Skeleton` composites for
// cover rendering (they handle procedural covers / boxart / aspect ratio
// via galleryViewStore) and builds v2 chrome around them.
import {
  RBtn,
  RDialog,
  REmptyState,
  RIcon,
  RProgressCircular,
  RSelect,
  RTextField,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import romApi from "@/services/api/rom";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms, { type SimpleRom, type SearchRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

type SourceName =
  | "IGDB"
  | "Mobygames"
  | "Screenscraper"
  | "Flashpoint"
  | "Launchbox"
  | "Libretro"
  | "SteamGridDB";

type MatchedSource = {
  url_cover: string | undefined;
  name: SourceName;
  logo_path: string;
};

type SourceFilter = {
  name: SourceName;
  label: string;
  logo: string;
  enabled: boolean;
  active: boolean;
};

const { t } = useI18n();
const { xs, lgAndUp } = useBreakpoint();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const romsStore = storeRoms();
const searching = ref(false);
const route = useRoute();
const searchText = ref("");
const searchBy = ref<"Name" | "ID">("Name");
const searched = ref(false);
const matchedRoms = ref<SearchRom[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const showSelectSource = ref(false);
const renameFromSource = ref(false);
const selectedMatchRom = ref<SearchRom | undefined>(undefined);
const selectedCover = ref<MatchedSource | undefined>(undefined);
const sources = ref<MatchedSource[]>([]);
const heartbeat = storeHeartbeat();

const isIGDBFiltered = ref(true);
const isMobyFiltered = ref(true);
const isSSFiltered = ref(true);
const isFlashpointFiltered = ref(true);
const isLaunchboxFiltered = ref(true);
const isLibretroFiltered = ref(true);

const sourceFilters = computed<SourceFilter[]>(() => [
  {
    name: "IGDB",
    label: "IGDB",
    logo: "/assets/scrappers/igdb.png",
    enabled: !!heartbeat.value.METADATA_SOURCES.IGDB_API_ENABLED,
    active: isIGDBFiltered.value,
  },
  {
    name: "Mobygames",
    label: "MobyGames",
    logo: "/assets/scrappers/moby.png",
    enabled: !!heartbeat.value.METADATA_SOURCES.MOBY_API_ENABLED,
    active: isMobyFiltered.value,
  },
  {
    name: "Screenscraper",
    label: "Screenscraper",
    logo: "/assets/scrappers/ss.png",
    enabled: !!heartbeat.value.METADATA_SOURCES.SS_API_ENABLED,
    active: isSSFiltered.value,
  },
  {
    name: "Launchbox",
    label: "Launchbox",
    logo: "/assets/scrappers/launchbox.png",
    enabled: !!heartbeat.value.METADATA_SOURCES.LAUNCHBOX_API_ENABLED,
    active: isLaunchboxFiltered.value,
  },
  {
    name: "Flashpoint",
    label: "Flashpoint",
    logo: "/assets/scrappers/flashpoint.png",
    enabled: !!heartbeat.value.METADATA_SOURCES.FLASHPOINT_API_ENABLED,
    active: isFlashpointFiltered.value,
  },
  {
    name: "Libretro",
    label: "Libretro",
    logo: "/assets/scrappers/libretro.png",
    enabled: !!heartbeat.value.METADATA_SOURCES.LIBRETRO_API_ENABLED,
    active: isLibretroFiltered.value,
  },
]);

function toggleSourceFilter(name: SourceName) {
  const source = sourceFilters.value.find((s) => s.name === name);
  if (!source || !source.enabled) return;
  if (name === "IGDB") isIGDBFiltered.value = !isIGDBFiltered.value;
  else if (name === "Mobygames") isMobyFiltered.value = !isMobyFiltered.value;
  else if (name === "Screenscraper") isSSFiltered.value = !isSSFiltered.value;
  else if (name === "Flashpoint")
    isFlashpointFiltered.value = !isFlashpointFiltered.value;
  else if (name === "Launchbox")
    isLaunchboxFiltered.value = !isLaunchboxFiltered.value;
  else if (name === "Libretro")
    isLibretroFiltered.value = !isLibretroFiltered.value;
}

const filteredMatchedRoms = computed(() =>
  matchedRoms.value.filter(
    (r) =>
      (r.igdb_id && isIGDBFiltered.value) ||
      (r.moby_id && isMobyFiltered.value) ||
      (r.ss_id && isSSFiltered.value) ||
      (r.flashpoint_id && isFlashpointFiltered.value) ||
      (r.launchbox_id && isLaunchboxFiltered.value) ||
      (r.libretro_id && isLibretroFiltered.value),
  ),
);

const openHandler = (romToSearch: SimpleRom) => {
  rom.value = romToSearch;
  show.value = true;
  matchedRoms.value = [];
  searched.value = false;
  searchText.value = romToSearch.is_identified
    ? (romToSearch.name ?? "")
    : romToSearch.fs_name_no_tags;
};
emitter?.on("showMatchRomDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showMatchRomDialog", openHandler));

async function searchRom() {
  showSelectSource.value = false;
  sources.value = [];
  if (!rom.value || searching.value) return;

  const inputElement = document.getElementById("r-v2-match-search");
  inputElement?.blur();

  searching.value = true;
  try {
    const response = await romApi.searchRom({
      romId: rom.value.id,
      searchTerm: searchText.value,
      searchBy: searchBy.value,
    });
    matchedRoms.value = response.data;
  } catch (error: unknown) {
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(axiosErr.response?.data?.detail ?? "Search failed", {
      icon: "mdi-close-circle",
    });
  } finally {
    searching.value = false;
    searched.value = true;
  }
}

function showSources(matchedRom: SearchRom) {
  if (!rom.value) return;
  showSelectSource.value = true;
  selectedMatchRom.value = matchedRom;
  sources.value = [];

  const push = (url: string | undefined, name: SourceName, logo: string) => {
    if (url) sources.value.push({ url_cover: url, name, logo_path: logo });
  };
  push(matchedRom.igdb_url_cover, "IGDB", "/assets/scrappers/igdb.png");
  push(matchedRom.moby_url_cover, "Mobygames", "/assets/scrappers/moby.png");
  push(matchedRom.ss_url_cover, "Screenscraper", "/assets/scrappers/ss.png");
  push(matchedRom.sgdb_url_cover, "SteamGridDB", "/assets/scrappers/sgdb.png");
  push(
    matchedRom.flashpoint_url_cover,
    "Flashpoint",
    "/assets/scrappers/flashpoint.png",
  );
  push(
    matchedRom.launchbox_url_cover,
    "Launchbox",
    "/assets/scrappers/launchbox.png",
  );
  push(
    matchedRom.libretro_url_cover,
    "Libretro",
    "/assets/scrappers/libretro.png",
  );

  if (sources.value.length === 1) selectedCover.value = sources.value[0];
}

function selectCover(source: MatchedSource) {
  selectedCover.value = source;
}

function confirm() {
  if (!selectedMatchRom.value) return;
  updateRom(selectedMatchRom.value, selectedCover.value?.url_cover);
  closeDialog();
}

function toggleRenameAsSource() {
  renameFromSource.value = !renameFromSource.value;
}

function backToMatched() {
  showSelectSource.value = false;
  selectedCover.value = undefined;
  selectedMatchRom.value = undefined;
  sources.value = [];
  renameFromSource.value = false;
}

async function updateRom(selectedRom: SearchRom, urlCover: string | undefined) {
  if (!rom.value) return;
  show.value = false;
  emitter?.emit("showLoadingDialog", { loading: true, scrim: true });

  rom.value = {
    ...rom.value,
    fs_name:
      renameFromSource.value && selectedMatchRom.value
        ? rom.value.fs_name.replace(
            rom.value.fs_name_no_tags,
            selectedMatchRom.value.name,
          )
        : rom.value.fs_name,
    igdb_id: selectedRom.igdb_id || null,
    ss_id: selectedRom.ss_id || null,
    moby_id: selectedRom.moby_id || null,
    flashpoint_id: selectedRom.flashpoint_id || null,
    launchbox_id: selectedRom.launchbox_id || null,
    libretro_id: selectedRom.libretro_id || null,
    name: selectedRom.name || null,
    slug: selectedRom.slug || null,
    summary: selectedRom.summary || null,
    url_cover:
      urlCover ||
      selectedRom.igdb_url_cover ||
      selectedRom.ss_url_cover ||
      selectedRom.moby_url_cover ||
      selectedRom.flashpoint_url_cover ||
      selectedRom.launchbox_url_cover ||
      selectedRom.libretro_url_cover ||
      null,
  };

  if (rom.value.url_cover) {
    rom.value.url_cover = rom.value.url_cover.replace("t_cover_big", "t_1080p");
  }

  try {
    const { data } = await romApi.updateRom({ rom: rom.value });
    snackbar.success("Rom updated successfully!", { icon: "mdi-check-bold" });
    romsStore.update(data as SimpleRom);
    if (route.name === "rom") romsStore.currentRom = data;
  } catch (error: unknown) {
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(axiosErr.response?.data?.detail ?? "Update failed", {
      icon: "mdi-close-circle",
    });
  } finally {
    emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
  }
}

function closeDialog() {
  show.value = false;
  searching.value = false;
  searched.value = false;
  searchBy.value = "Name";
  sources.value = [];
  showSelectSource.value = false;
  selectedCover.value = undefined;
  selectedMatchRom.value = undefined;
  renameFromSource.value = false;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-search-web"
    scroll-content
    :width="lgAndUp ? 880 : '95vw'"
    :height="xs ? '82vh' : '88vh'"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.match-rom") }}</span>
    </template>

    <template #toolbar>
      <div class="r-v2-match__toolbar">
        <div class="r-v2-match__filters">
          <span class="r-v2-match__filters-label">
            {{ t("common.filter") }}
          </span>
          <button
            v-for="f in sourceFilters"
            :key="f.name"
            type="button"
            class="r-v2-match__filter"
            :class="{
              'r-v2-match__filter--active': f.active && f.enabled,
              'r-v2-match__filter--disabled': !f.enabled,
            }"
            :title="
              f.enabled
                ? `Filter ${f.label} matches`
                : `${f.label} source is not enabled`
            "
            :disabled="!f.enabled"
            @click="toggleSourceFilter(f.name)"
          >
            <img :src="f.logo" :alt="f.label" />
          </button>
          <div class="r-v2-match__results">
            <span>{{ t("rom.results-found") }}</span>
            <span class="r-v2-match__results-count">
              {{ searching ? "…" : filteredMatchedRoms.length }}
            </span>
          </div>
        </div>

        <div class="r-v2-match__search-row">
          <RTextField
            id="r-v2-match-search"
            v-model="searchText"
            prefix-label="inline"
            :placeholder="t('common.search')"
            :disabled="searching"
            density="comfortable"
            hide-details
            clearable
            @keyup.enter="searchRom"
          >
            <template #prefix-label>
              <RIcon icon="mdi-magnify" size="14" />
            </template>
          </RTextField>
          <RSelect
            v-model="searchBy"
            :disabled="searching"
            :label="t('rom.by')"
            variant="outlined"
            density="comfortable"
            hide-details
            :items="['ID', 'Name']"
            class="r-v2-match__by"
          />
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-search-web"
            :loading="searching"
            :disabled="searching"
            @click="searchRom"
          >
            {{ t("common.search") }}
          </RBtn>
        </div>
      </div>
    </template>

    <template #content>
      <!-- Loading — searching the metadata providers. -->
      <div v-if="searching" class="r-v2-match__state">
        <RProgressCircular indeterminate :size="40" />
      </div>

      <!-- Empty — search ran but nothing matched. -->
      <REmptyState
        v-else-if="searched && matchedRoms.length === 0"
        icon="mdi-disc-alert"
        :title="t('common.no-results')"
        :hint="t('rom.results-found')"
      />

      <template v-else-if="!showSelectSource">
        <div v-if="rom" class="r-v2-match__grid">
          <GameCard
            v-for="matchedRom in filteredMatchedRoms"
            :key="`${matchedRom.igdb_id}-${matchedRom.moby_id}-${matchedRom.ss_id}-${matchedRom.name}`"
            :rom="matchedRom as unknown as SimpleRom"
            static
            class="r-v2-match__card"
            @click="showSources(matchedRom)"
          />
        </div>
      </template>

      <template v-else>
        <div class="r-v2-match__detail">
          <header class="r-v2-match__detail-head">
            <button
              type="button"
              class="r-v2-match__back"
              aria-label="Back"
              @click="backToMatched"
            >
              <RIcon icon="mdi-arrow-left" size="18" />
            </button>
            <div>
              <h3 class="r-v2-match__detail-title">
                {{ selectedMatchRom?.name }}
              </h3>
              <p
                v-if="selectedMatchRom?.summary"
                class="r-v2-match__detail-summary"
              >
                {{ selectedMatchRom.summary }}
              </p>
            </div>
          </header>

          <p v-if="sources.length > 1" class="r-v2-match__sources-label">
            {{ t("rom.select-cover-image") }}
          </p>

          <div class="r-v2-match__sources">
            <GameCard
              v-for="source in sources"
              :key="source.name"
              :rom="{ id: 0, name: source.name } as unknown as SimpleRom"
              :cover-src="source.url_cover"
              :selected="selectedCover?.name === source.name"
              static
              @click="selectCover(source)"
            >
              <template #overlay>
                <div class="r-v2-match__source-logo">
                  <img :src="source.logo_path" :alt="source.name" />
                </div>
              </template>
            </GameCard>
          </div>

          <button
            v-if="selectedMatchRom"
            type="button"
            class="r-v2-match__rename"
            :class="{ 'r-v2-match__rename--disabled': !selectedCover }"
            :aria-pressed="renameFromSource"
            :disabled="!selectedCover"
            @click="toggleRenameAsSource"
          >
            <RIcon
              :icon="
                renameFromSource
                  ? 'mdi-checkbox-outline'
                  : 'mdi-checkbox-blank-outline'
              "
              size="15"
            />
            {{ t("rom.rename-file-title", { source: selectedCover?.name }) }}
          </button>

          <p
            v-if="rom && renameFromSource && selectedMatchRom"
            class="r-v2-match__rename-preview"
          >
            {{
              t("rom.rename-file-details", {
                from: rom.fs_name,
                to: rom.fs_name.replace(
                  rom.fs_name_no_tags,
                  selectedMatchRom.name,
                ),
              })
            }}
          </p>
        </div>
      </template>
    </template>

    <template #footer>
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        v-if="showSelectSource"
        variant="translucent"
        color="primary"
        prepend-icon="mdi-check"
        :disabled="!selectedMatchRom"
        @click="confirm"
      >
        {{ t("common.confirm") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-match__toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.r-v2-match__filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.r-v2-match__filters-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--r-color-fg-muted);
  margin-right: 4px;
}

.r-v2-match__filter {
  appearance: none;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border-strong);
  width: 32px;
  height: 32px;
  border-radius: var(--r-radius-sm);
  padding: 2px;
  cursor: pointer;
  display: grid;
  place-items: center;
  opacity: 0.4;
  transition:
    opacity var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-match__filter img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.r-v2-match__filter--active {
  opacity: 1;
  border-color: var(--r-color-brand-primary);
}
.r-v2-match__filter--disabled {
  cursor: not-allowed;
}

.r-v2-match__results {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  color: var(--r-color-fg-secondary);
}
.r-v2-match__results-count {
  padding: 2px 8px;
  background: color-mix(in srgb, var(--r-color-brand-primary) 20%, transparent);
  color: var(--r-color-brand-primary);
  border-radius: var(--r-radius-pill);
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-match__search-row {
  display: grid;
  grid-template-columns: 1fr 140px auto;
  gap: 8px;
  align-items: stretch;
}

.r-v2-match__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}

/* Centred slot for the loading spinner / empty state — fills the
   remaining body height so the dialog doesn't collapse to the spinner. */
.r-v2-match__state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.r-v2-match__card {
  cursor: pointer;
}

.r-v2-match__detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-match__detail-head {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.r-v2-match__back {
  appearance: none;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  color: var(--r-color-fg-secondary);
  width: 32px;
  height: 32px;
  border-radius: var(--r-radius-sm);
  display: grid;
  place-items: center;
  cursor: pointer;
  flex-shrink: 0;
}
.r-v2-match__back:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}

.r-v2-match__detail-title {
  margin: 0;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-match__detail-summary {
  margin: 4px 0 0;
  color: var(--r-color-fg-secondary);
  font-size: 12px;
  line-height: 1.5;
  max-height: 120px;
  overflow-y: auto;
}

.r-v2-match__sources-label {
  margin: 4px 0 0;
  text-align: center;
  color: var(--r-color-fg-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.r-v2-match__sources {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
}

.r-v2-match__source-logo {
  width: 28px;
  height: 28px;
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 85%,
    transparent
  );
  border-radius: var(--r-radius-sm);
  padding: 3px;
  display: grid;
  place-items: center;
  margin: 4px;
}
.r-v2-match__source-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.r-v2-match__rename {
  appearance: none;
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 12px;
  font-family: inherit;
  color: var(--r-color-fg-secondary);
  cursor: pointer;
}
.r-v2-match__rename:hover:not(:disabled) {
  background: var(--r-color-surface-hover);
}
.r-v2-match__rename--disabled,
.r-v2-match__rename:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.r-v2-match__rename-preview {
  margin: 0;
  padding: 8px 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-sm);
  font-size: 11px;
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-muted);
  text-align: center;
  word-break: break-all;
}

@media (max-width: 600px) {
  .r-v2-match__search-row {
    grid-template-columns: 1fr;
  }
}
</style>
