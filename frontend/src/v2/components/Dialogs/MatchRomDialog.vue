<script setup lang="ts">
// MatchRomDialog — manual metadata match flow. The shell owns search +
// filters + the update API call; the actual "pick a match → pick a
// cover → optional rename" step is delegated to one of two body
// variants (see `components/MatchRom/`): grid (cards + overlay) or
// list (master/detail). The variant is switchable at runtime via the
// segmented control in the toolbar, mirroring the gallery's
// grid/list toggle.
import {
  RBtn,
  RDialog,
  RIcon,
  RSelect,
  RSliderBtnGroup,
  RSpinner,
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
import MatchRomBodyGrid from "@/v2/components/MatchRom/MatchRomBodyGrid.vue";
import MatchRomBodyList from "@/v2/components/MatchRom/MatchRomBodyList.vue";
import MatchRomProviderFilter from "@/v2/components/MatchRom/MatchRomProviderFilter.vue";
import type {
  ConfirmPayload,
  MatchVariant,
} from "@/v2/components/MatchRom/types";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

type SourceName =
  | "IGDB"
  | "Mobygames"
  | "Screenscraper"
  | "Flashpoint"
  | "Launchbox"
  | "Libretro";

type SourceFilter = {
  name: SourceName;
  label: string;
  logo: string;
  enabled: boolean;
  active: boolean;
};

const { t } = useI18n();
const { lgAndUp } = useBreakpoint();
const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const romsStore = storeRoms();
const searching = ref(false);
// In-flight flag for the post-pick `updateRom` call. v1 leaned on the
// global `showLoadingDialog` event for feedback, but v2 has no listener
// for it, so the dialog used to close instantly and the user had no
// idea the network call was running. Keeping the dialog open with a
// spinner overlay matches the v2 pattern (inline loading, §VI.B).
const matching = ref(false);
const route = useRoute();
const searchText = ref("");
const searchBy = ref<"Name" | "ID">("Name");
const searched = ref(false);
const matchedRoms = ref<SearchRom[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const heartbeat = storeHeartbeat();

// Active body variant — the toolbar selector toggles between the
// gallery-style grid and the master/detail list, mirroring the
// gallery's own layout switcher vocabulary.
const variant = ref<MatchVariant>("grid");

const variantItems = computed<
  Array<{
    id: MatchVariant;
    icon: string;
    ariaLabel: string;
    title: string;
  }>
>(() => [
  {
    id: "grid",
    icon: "mdi-view-grid-outline",
    ariaLabel: t("rom.match-rom-grid-label"),
    title: t("rom.match-rom-grid-title"),
  },
  {
    id: "list",
    icon: "mdi-view-list",
    ariaLabel: t("rom.match-rom-list-label"),
    title: t("rom.match-rom-list-title"),
  },
]);

const variantComponent = computed(() =>
  variant.value === "list" ? MatchRomBodyList : MatchRomBodyGrid,
);

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
    snackbar.error(axiosErr.response?.data?.detail ?? t("rom.search-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    searching.value = false;
    searched.value = true;
  }
}

async function onBodyConfirm(payload: ConfirmPayload) {
  if (!rom.value || matching.value) return;
  matching.value = true;

  const { matchedRom, cover, renameFromSource } = payload;
  rom.value = {
    ...rom.value,
    fs_name: renameFromSource
      ? rom.value.fs_name.replace(rom.value.fs_name_no_tags, matchedRom.name)
      : rom.value.fs_name,
    igdb_id: matchedRom.igdb_id || null,
    ss_id: matchedRom.ss_id || null,
    moby_id: matchedRom.moby_id || null,
    flashpoint_id: matchedRom.flashpoint_id || null,
    launchbox_id: matchedRom.launchbox_id || null,
    libretro_id: matchedRom.libretro_id || null,
    name: matchedRom.name || null,
    slug: matchedRom.slug || null,
    summary: matchedRom.summary || null,
    url_cover:
      cover?.url_cover ||
      matchedRom.igdb_url_cover ||
      matchedRom.ss_url_cover ||
      matchedRom.moby_url_cover ||
      matchedRom.flashpoint_url_cover ||
      matchedRom.launchbox_url_cover ||
      matchedRom.libretro_url_cover ||
      null,
  };

  if (rom.value.url_cover) {
    rom.value.url_cover = rom.value.url_cover.replace("t_cover_big", "t_1080p");
  }

  try {
    const { data } = await romApi.updateRom({ rom: rom.value });
    snackbar.success(t("rom.rom-updated-successfully"), {
      icon: "mdi-check-bold",
    });
    romsStore.update(data as SimpleRom);
    if (route.name === "rom") romsStore.currentRom = data;
  } catch (error: unknown) {
    const axiosErr = error as { response?: { data?: { detail?: string } } };
    snackbar.error(axiosErr.response?.data?.detail ?? t("rom.update-failed"), {
      icon: "mdi-close-circle",
    });
  } finally {
    matching.value = false;
    closeDialog();
  }
}

function closeDialog() {
  show.value = false;
  searching.value = false;
  searched.value = false;
  searchBy.value = "Name";
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-search-web"
    scroll-content
    full-height-on-mobile
    :width="lgAndUp ? 880 : '95vw'"
    height="88vh"
    :persistent="matching"
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
          <MatchRomProviderFilter
            v-for="f in sourceFilters"
            :key="f.name"
            :name="f.name"
            :label="f.label"
            :logo="f.logo"
            :enabled="f.enabled"
            :active="f.active"
            @toggle="toggleSourceFilter(f.name)"
          />

          <!-- Layout switcher — grid vs list. Mirrors the gallery's own
               toggle. Pushed right and always present, so the provider chips
               stay flush left and the row never reflows on search (the
               results count now lives in the footer). -->
          <div class="r-v2-match__filters-end">
            <RSliderBtnGroup
              :model-value="variant"
              :items="variantItems"
              variant="segmented"
              :aria-label="t('rom.match-flow-variant')"
              @update:model-value="variant = $event"
            />
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
            :label="t('rom.match-by-label')"
            variant="outlined"
            density="comfortable"
            hide-details
            :items="[
              { title: t('rom.search-by-id'), value: 'ID' },
              { title: t('rom.search-by-name'), value: 'Name' },
            ]"
            class="r-v2-match__by"
          />
          <RBtn
            variant="flat"
            color="primary"
            prepend-icon="mdi-search-web"
            class="r-v2-match__search-btn"
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
      <div class="r-v2-match__body">
        <component
          :is="variantComponent"
          :rom="rom"
          :results="filteredMatchedRoms"
          :searching="searching"
          :searched="searched"
          @confirm="onBodyConfirm"
        />
        <!-- Saving overlay — covers the body with a centered spinner so
             the user sees the update is in flight. The dialog stays
             modal (no scrim click / Escape) until closeDialog runs in
             the `finally` of `onBodyConfirm`. -->
        <div
          v-if="matching"
          class="r-v2-match__saving"
          role="status"
          aria-live="polite"
        >
          <RSpinner :size="36" />
          <span class="r-v2-match__saving-label">
            {{ t("rom.updating") }}
          </span>
        </div>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="matching" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div class="r-v2-match__footer-spacer" />
      <!-- Results count lives here (not the filter row) so appearing after a
           search never reflows the toolbar above. -->
      <div v-if="searched && !searching" class="r-v2-match__results">
        <span>{{ t("rom.results-found") }}</span>
        <span class="r-v2-match__results-count">
          {{ filteredMatchedRoms.length }}
        </span>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
/* Saving-overlay anchor — has to pass the dialog body's column layout
   through (`flex: 1`, `min-height: 0`, `display: flex; flex-direction:
   column`) so the variant inside still sees the same shape it would
   have as a direct child of `.r-dialog__body`. Without this, grid /
   list bodies that rely on `flex: 1` to fill the dialog collapse to
   their content size — the grid's secondary detail panel anchors to
   the wrong rect (it's `position: absolute` against `.match-grid`),
   and the list's two columns lose their internal scroll. */
.r-v2-match__body {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.r-v2-match__saving {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: color-mix(in srgb, var(--r-color-bg) 65%, transparent);
  backdrop-filter: blur(4px);
  color: var(--r-color-fg);
  z-index: 1;
}

.r-v2-match__saving-label {
  font-size: 13px;
  color: var(--r-color-fg-secondary);
}

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

.r-v2-match__filters-end {
  /* Pushes the variant switcher to the right of the filter row; always
     present, so the switcher never slides as the search state changes. */
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.r-v2-match__results {
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

.r-v2-match__footer-spacer {
  flex: 1 1 auto;
}

.r-v2-match__search-row {
  display: grid;
  grid-template-columns: 1fr 140px auto;
  gap: 8px;
  align-items: stretch;
}
/* Grid children default to `min-width: auto`, so each track can't shrink below
   its content's min width. The search field's min width changes when its
   `clear` button appears/disappears (e.g. once a search disables the field),
   which would otherwise steal/return width from the fixed selector track and
   make the name/id selector visibly jump. `min-width: 0` pins the tracks to
   their declared sizes regardless of content. */
.r-v2-match__search-row > * {
  min-width: 0;
}

/* Phones: keep the text field (2/3) and the name/id selector (1/3) on one
   row; the search button drops to its own full-width row below. */
html[data-bp~="xs"] .r-v2-match__search-row {
  grid-template-columns: 2fr 1fr;
}
html[data-bp~="xs"] .r-v2-match__search-btn {
  grid-column: 1 / -1;
}
</style>
