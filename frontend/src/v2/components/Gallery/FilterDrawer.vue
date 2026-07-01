<script setup lang="ts">
// FilterDrawer (v2) — gallery filter side panel. v2-native replacement
// for `src/components/Gallery/AppBar/common/FilterDrawer/Base.vue`.
//
// Surface area (matches v1 1:1 so URLs stay compatible):
//   • Tri-state boolean filters: matched / favourites / duplicates /
//     playables / missing / verified / RA. Each maps null → "all",
//     true → positive, false → negative.
//   • Optional platform multi-select (only on Search / Collection views
//     where you can mix platforms).
//   • 11 multi-select filter groups (genres / franchises / collections /
//     companies / age-ratings / regions / languages / tags /
//     player-counts / metadata-providers / statuses) — each paired with
//     an AND/OR/NONE logic toggle.
//   • Reset button at the bottom.
//
// Apply is implicit — the URL composable + galleryRoms watcher refresh
// results on every store change. There is no "Apply" button.
//
// Feature composite — knows the galleryFilter store layout and v2
// primitives. Mounted by GalleryShell so it's available everywhere a
// gallery is rendered. The shell controls `modelValue` and forwards
// `showPlatformsFilter`.
import { RBtn, RDrawer, RIcon, RSelect, RSliderBtnGroup, RTag } from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter, {
  type FilterLogicOperator,
} from "@/stores/galleryFilter";
import storePlatforms, { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { romStatusMap, type PlayingStatus } from "@/utils";
import PlatformSelect from "@/v2/components/shared/PlatformSelect.vue";
import { METADATA_PROVIDER_FILTER_OPTIONS } from "@/v2/utils/metadataProviders";

defineOptions({ inheritAttrs: false });

interface Props {
  modelValue: boolean;
  /** Show the platforms multi-select. False on single-platform views. */
  showPlatformsFilter?: boolean;
}

withDefaults(defineProps<Props>(), {
  showPlatformsFilter: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
}>();

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const filter = storeGalleryFilter();
const platformsStore = storePlatforms();
const {
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterMissing,
  filterVerified,
  filterRA,
  filterSaves,
  filterStates,
  selectedPlatforms,
  filterGenres,
  selectedGenres,
  genresLogic,
  filterFranchises,
  selectedFranchises,
  franchisesLogic,
  filterCollections,
  selectedCollections,
  collectionsLogic,
  filterCompanies,
  selectedCompanies,
  companiesLogic,
  filterAgeRatings,
  selectedAgeRatings,
  ageRatingsLogic,
  filterRegions,
  selectedRegions,
  regionsLogic,
  filterLanguages,
  selectedLanguages,
  languagesLogic,
  filterPlayerCounts,
  selectedPlayerCounts,
  playerCountsLogic,
  selectedMetadataProviders,
  metadataProvidersLogic,
  filterTags,
  selectedTags,
  tagsLogic,
  filterStatuses,
  selectedStatuses,
  statusesLogic,
} = storeToRefs(filter);
const { allPlatforms } = storeToRefs(platformsStore);

// Provider options are a fixed registry (not data-derived like the other
// lists). Items are the provider slugs; `providerTitle` maps each to its
// brand name for display.
const providerItems = computed(() =>
  METADATA_PROVIDER_FILTER_OPTIONS.map((p) => p.value),
);
const providerLabels = new Map(
  METADATA_PROVIDER_FILTER_OPTIONS.map((p) => [p.value, p.title]),
);
const providerTitle = (slug: string): string =>
  providerLabels.get(slug) ?? slug;

// ── Tri-state mapping helpers ──────────────────────────────────
// The RSliderBtnGroup speaks string ids; the store speaks `boolean | null`.
// One helper makes the binding bidirectional in a few lines.
type TriValue = "all" | "yes" | "no";
function triFor(v: boolean | null): TriValue {
  if (v === true) return "yes";
  if (v === false) return "no";
  return "all";
}
function triToBool(v: TriValue): boolean | null {
  if (v === "yes") return true;
  if (v === "no") return false;
  return null;
}

interface BoolFilterConfig {
  label: string;
  icon: string;
  yesIcon: string;
  noIcon: string;
  yesAria: string;
  noAria: string;
  // The two-way ref of the underlying `boolean | null`.
  value: { value: boolean | null };
}

const boolFilters: BoolFilterConfig[] = [
  {
    label: t("platform.show-matched"),
    icon: "mdi-link-variant",
    yesIcon: "mdi-link-variant",
    noIcon: "mdi-link-variant-off",
    yesAria: t("platform.show-matched-only"),
    noAria: t("platform.show-unmatched-only"),
    value: filterMatched,
  },
  {
    label: t("platform.show-favorites"),
    icon: "mdi-star",
    yesIcon: "mdi-star",
    noIcon: "mdi-star-outline",
    yesAria: t("platform.show-favorites-only"),
    noAria: t("platform.show-not-favorites-only"),
    value: filterFavorites,
  },
  {
    label: t("platform.show-duplicates"),
    icon: "mdi-content-duplicate",
    yesIcon: "mdi-content-duplicate",
    noIcon: "mdi-checkbox-multiple-blank-outline",
    yesAria: t("platform.show-duplicates-only"),
    noAria: t("platform.show-not-duplicates-only"),
    value: filterDuplicates,
  },
  {
    label: t("platform.show-playables"),
    icon: "mdi-controller",
    yesIcon: "mdi-controller",
    noIcon: "mdi-controller-off",
    yesAria: t("platform.show-playables-only"),
    noAria: t("platform.show-not-playables-only"),
    value: filterPlayables,
  },
  {
    label: t("platform.show-missing"),
    icon: "mdi-file-question-outline",
    yesIcon: "mdi-file-question-outline",
    noIcon: "mdi-file-check-outline",
    yesAria: t("platform.show-missing-only"),
    noAria: t("platform.show-not-missing-only"),
    value: filterMissing,
  },
  {
    label: t("platform.show-verified"),
    icon: "mdi-check-decagram",
    yesIcon: "mdi-check-decagram",
    noIcon: "mdi-check-decagram-outline",
    yesAria: t("platform.show-verified-only"),
    noAria: t("platform.show-not-verified-only"),
    value: filterVerified,
  },
  {
    label: t("platform.show-ra"),
    icon: "mdi-trophy",
    yesIcon: "mdi-trophy",
    noIcon: "mdi-trophy-outline",
    yesAria: t("platform.show-ra-only"),
    noAria: t("platform.show-not-ra-only"),
    value: filterRA,
  },
  {
    label: t("platform.show-saves"),
    icon: "mdi-content-save-outline",
    yesIcon: "mdi-content-save-outline",
    noIcon: "mdi-content-save-off-outline",
    yesAria: t("platform.show-saves-only"),
    noAria: t("platform.show-not-saves-only"),
    value: filterSaves,
  },
  {
    label: t("platform.show-states"),
    icon: "mdi-camera-outline",
    yesIcon: "mdi-camera-outline",
    noIcon: "mdi-camera-off-outline",
    yesAria: t("platform.show-states-only"),
    noAria: t("platform.show-not-states-only"),
    value: filterStates,
  },
];

function setTri(cfg: BoolFilterConfig, v: TriValue) {
  cfg.value.value = triToBool(v);
}
function triItems(cfg: BoolFilterConfig) {
  return [
    {
      id: "all" as const,
      icon: "mdi-circle-outline",
      ariaLabel: t("platform.show-all"),
      title: t("common.all"),
    },
    {
      id: "yes" as const,
      icon: cfg.yesIcon,
      ariaLabel: cfg.yesAria,
      title: cfg.yesAria,
    },
    {
      id: "no" as const,
      icon: cfg.noIcon,
      ariaLabel: cfg.noAria,
      title: cfg.noAria,
    },
  ];
}

// ── Multi-select sections ──────────────────────────────────────
// One config drives both rendering and the logic toggle. Items come
// from the filter store (populated by galleryRoms when fetching).
interface MultiConfig {
  label: string;
  icon: string;
  items: { value: string[] };
  selected: { value: string[] };
  logic: { value: FilterLogicOperator };
  setLogic: (logic: FilterLogicOperator) => void;
  /** Optional title transformer (Statuses use a friendly label). */
  toTitle?: (raw: string) => string;
}

const statusTitle = (raw: string): string => {
  const entry = romStatusMap[raw as PlayingStatus];
  return entry ? entry.text : raw;
};

const multiSections = computed<MultiConfig[]>(() => [
  {
    label: t("platform.genre"),
    icon: "mdi-shape-outline",
    items: filterGenres,
    selected: selectedGenres,
    logic: genresLogic,
    setLogic: (l) => filter.setGenresLogic(l),
  },
  {
    label: t("platform.franchise"),
    icon: "mdi-bookshelf",
    items: filterFranchises,
    selected: selectedFranchises,
    logic: franchisesLogic,
    setLogic: (l) => filter.setFranchisesLogic(l),
  },
  {
    label: t("platform.collection"),
    icon: "mdi-bookmark-outline",
    items: filterCollections,
    selected: selectedCollections,
    logic: collectionsLogic,
    setLogic: (l) => filter.setCollectionsLogic(l),
  },
  {
    label: t("platform.company"),
    icon: "mdi-domain",
    items: filterCompanies,
    selected: selectedCompanies,
    logic: companiesLogic,
    setLogic: (l) => filter.setCompaniesLogic(l),
  },
  {
    label: t("platform.age-rating"),
    icon: "mdi-account-child",
    items: filterAgeRatings,
    selected: selectedAgeRatings,
    logic: ageRatingsLogic,
    setLogic: (l) => filter.setAgeRatingsLogic(l),
  },
  {
    label: t("platform.region"),
    icon: "mdi-earth",
    items: filterRegions,
    selected: selectedRegions,
    logic: regionsLogic,
    setLogic: (l) => filter.setRegionsLogic(l),
  },
  {
    label: t("platform.language"),
    icon: "mdi-translate",
    items: filterLanguages,
    selected: selectedLanguages,
    logic: languagesLogic,
    setLogic: (l) => filter.setLanguagesLogic(l),
  },
  {
    label: t("platform.tag"),
    icon: "mdi-tag-outline",
    items: filterTags,
    selected: selectedTags,
    logic: tagsLogic,
    setLogic: (l) => filter.setTagsLogic(l),
  },
  {
    label: t("platform.player-count"),
    icon: "mdi-account-group",
    items: filterPlayerCounts,
    selected: selectedPlayerCounts,
    logic: playerCountsLogic,
    setLogic: (l) => filter.setPlayerCountsLogic(l),
  },
  {
    label: t("platform.metadata-provider"),
    icon: "mdi-database-outline",
    items: providerItems,
    selected: selectedMetadataProviders,
    logic: metadataProvidersLogic,
    setLogic: (l) => filter.setMetadataProvidersLogic(l),
    toTitle: providerTitle,
  },
  {
    label: t("platform.status"),
    icon: "mdi-flag-outline",
    items: filterStatuses,
    selected: selectedStatuses,
    logic: statusesLogic,
    setLogic: (l) => filter.setStatusesLogic(l),
    toTitle: statusTitle,
  },
]);

const LOGIC_ITEMS = computed(() => [
  {
    id: "any" as const,
    icon: "mdi-set-all",
    ariaLabel: t("platform.match-any-logic"),
    title: t("platform.match-any-logic"),
  },
  {
    id: "all" as const,
    icon: "mdi-set-center",
    ariaLabel: t("platform.match-all-logic"),
    title: t("platform.match-all-logic"),
  },
  {
    id: "none" as const,
    icon: "mdi-set-none",
    ariaLabel: t("platform.match-none-logic"),
    title: t("platform.match-none-logic"),
  },
]);

// ── Platform multi-select ──────────────────────────────────────
const selectedPlatformIds = computed({
  get: () => selectedPlatforms.value.map((p) => p.id),
  set: (ids: number[]) => {
    const looked = ids
      .map((id) => allPlatforms.value.find((p) => p.id === id))
      .filter((p): p is Platform => Boolean(p));
    filter.setSelectedFilterPlatforms(looked);
  },
});

// ── Active-filter count (footer badge) ────────────────────────
const activeCount = computed(() => {
  let n = 0;
  for (const f of boolFilters) if (f.value.value !== null) n += 1;
  if (selectedPlatforms.value.length > 0) n += 1;
  for (const s of multiSections.value) if (s.selected.value.length > 0) n += 1;
  return n;
});

function close() {
  emit("update:modelValue", false);
}

function resetAll() {
  for (const f of boolFilters) f.value.value = null;
  filter.setSelectedFilterPlatforms([]);
  for (const s of multiSections.value) {
    s.selected.value = [];
    s.setLogic("any");
  }
}

// Hand off to CreateSmartCollectionDialog — closing the drawer first
// keeps focus management clean (the drawer's escape stack pops before
// the dialog pushes its own).
function saveAsSmartCollection() {
  emit("update:modelValue", false);
  emitter?.emit("showCreateSmartCollectionDialog", null);
}
</script>

<template>
  <RDrawer
    :model-value="modelValue"
    side="right"
    :width="440"
    icon="mdi-filter-variant"
    hide-close
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <template #header>
      <span>{{ t("platform.filters") }}</span>
      <RTag v-if="activeCount > 0" tone="brand" size="x-small">
        {{ activeCount }}
      </RTag>
      <div style="flex: 1" />
      <RBtn
        size="small"
        variant="text"
        color="primary"
        prepend-icon="mdi-playlist-plus"
        :disabled="activeCount === 0"
        @click="saveAsSmartCollection"
      >
        {{ t("collection.save-as-smart") }}
      </RBtn>
    </template>

    <!-- ── Boolean tri-state filters ────────────────────────── -->
    <section class="r-v2-fd__section">
      <h3 class="r-v2-fd__heading">
        {{ t("platform.show") }}
      </h3>
      <div class="r-v2-fd__bool-rows">
        <div
          v-for="(cfg, idx) in boolFilters"
          :key="idx"
          class="r-v2-fd__bool-row"
          :class="{ 'r-v2-fd__bool-row--on': cfg.value.value !== null }"
        >
          <span class="r-v2-fd__bool-label">
            <RIcon :icon="cfg.icon" size="16" />
            <span>{{ cfg.label }}</span>
          </span>
          <RSliderBtnGroup
            :model-value="triFor(cfg.value.value)"
            :items="triItems(cfg)"
            size="small"
            @update:model-value="(v: TriValue) => setTri(cfg, v)"
          />
        </div>
      </div>
    </section>

    <!-- ── Platforms (optional) ─────────────────────────────── -->
    <section v-if="showPlatformsFilter" class="r-v2-fd__section">
      <h3 class="r-v2-fd__heading">{{ t("common.platforms") }}</h3>
      <PlatformSelect
        v-model="selectedPlatformIds"
        :items="allPlatforms"
        multiple
        clearable
        hide-details
        prefix-label="stacked"
        :placeholder="t('common.all-platforms')"
      >
        <template #prefix-label>
          <RIcon icon="mdi-monitor" size="14" />
          {{ t("common.platforms") }}
        </template>
      </PlatformSelect>
    </section>

    <!-- ── Multi-select groups + logic toggle ──────────────── -->
    <section class="r-v2-fd__section">
      <h3 class="r-v2-fd__heading">{{ t("platform.tags") }}</h3>
      <div class="r-v2-fd__multi-rows">
        <div
          v-for="s in multiSections"
          :key="s.label"
          class="r-v2-fd__multi-row"
        >
          <RSelect
            :model-value="s.selected.value"
            :items="
              s.items.value.map((raw) => ({
                title: s.toTitle ? s.toTitle(raw) : raw,
                value: raw,
              }))
            "
            multiple
            searchable
            clearable
            hide-details
            prefix-label="stacked"
            class="r-v2-fd__multi-select"
            @update:model-value="(v) => (s.selected.value = v as string[])"
          >
            <template #prefix-label>
              <RIcon :icon="s.icon" size="14" />
              {{ s.label }}
            </template>
          </RSelect>
          <RSliderBtnGroup
            :model-value="s.logic.value"
            :items="LOGIC_ITEMS"
            size="small"
            class="r-v2-fd__logic"
            @update:model-value="(v: FilterLogicOperator) => s.setLogic(v)"
          />
        </div>
      </div>
    </section>

    <template #footer>
      <RBtn
        variant="text"
        color="danger"
        prepend-icon="mdi-restore"
        :disabled="activeCount === 0"
        @click="resetAll"
      >
        {{ t("platform.reset-filters") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn variant="flat" color="primary" @click="close">
        {{ t("common.close") }}
      </RBtn>
    </template>
  </RDrawer>
</template>

<style scoped>
.r-v2-fd__section {
  padding: 14px 0;
  border-bottom: 1px solid var(--r-color-border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-fd__section:first-of-type {
  padding-top: 0;
}
.r-v2-fd__section:last-of-type {
  border-bottom: 0;
  padding-bottom: 0;
}

.r-v2-fd__heading {
  margin: 0;
  padding: 0 2px;
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

/* ── Boolean rows ────────────────────────────────────────────── */
.r-v2-fd__bool-rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-fd__bool-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 4px;
  border-radius: 8px;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-fd__bool-row--on {
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.r-v2-fd__bool-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--r-color-fg-secondary);
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
}
.r-v2-fd__bool-row--on .r-v2-fd__bool-label {
  color: var(--r-color-brand-primary);
}

/* ── Multi-select rows ───────────────────────────────────────── */
.r-v2-fd__multi-rows {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.r-v2-fd__multi-row {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  gap: 8px;
}
.r-v2-fd__multi-select {
  min-width: 0;
}
.r-v2-fd__logic {
  flex-shrink: 0;
  /* Visually align with the select's field box (the stacked label
     sits above, so the row baseline is the field, not the label). */
}
</style>
