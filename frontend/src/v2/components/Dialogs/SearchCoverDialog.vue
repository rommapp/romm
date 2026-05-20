<script setup lang="ts">
// SearchCoverDialog — global SteamGridDB cover-search dialog. Listens
// for the `showSearchCoverDialog` emitter event (term + optional
// platformId), queries `sgdbApi.searchCover`, and groups the results
// per-game in an `RCollapsible` accordion. Picking a cover thumb fires
// `updateUrlCover` with the full-resolution URL; consumers (EditRom,
// CollectionSettingsDrawer) listen for that event scoped to their own
// open lifecycle.
//
// Replaces v1's `SearchCover.vue` 1:1 in functionality, with v2 chrome:
// `RDialog`, `RCollapsible`, `RTextField`, `RSelect`, `REmptyState`,
// `RSpinner`. No `v-expansion-panels`, no Vuetify primitives.
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SearchCoverSchema } from "@/__generated__";
import sgdbApi from "@/services/api/sgdb";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RSelect from "@/v2/lib/forms/RSelect/RSelect.vue";
import RTextField from "@/v2/lib/forms/RTextField/RTextField.vue";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import REmptyState from "@/v2/lib/primitives/REmptyState/REmptyState.vue";
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

const coverTypeItems = [
  { title: "All", value: "all" },
  { title: "Static", value: "static" },
  { title: "Animated", value: "animated" },
];

// Filter happens after the search returns — splitting the source list
// and the visible list keeps the type-filter snappy without re-hitting
// the API for every flip.
const filteredCovers = computed<SearchCoverSchema[]>(() => {
  if (coverType.value === "all") return covers.value;
  return covers.value
    .map((game) => ({
      ...game,
      resources: game.resources.filter((r) => r.type === coverType.value),
    }))
    .filter((g) => g.resources.length > 0);
});

const hasResults = computed(() => filteredCovers.value.length > 0);
const showEmpty = computed(
  () => !searching.value && searchText.value.length > 0 && !hasResults.value,
);

function openHandler({ term }: { term: string; platformId?: number }) {
  searchText.value = term;
  covers.value = [];
  show.value = true;
  if (searchText.value) doSearch();
}
emitter?.on("showSearchCoverDialog", openHandler);
onBeforeUnmount(() => emitter?.off("showSearchCoverDialog", openHandler));

async function doSearch() {
  if (searching.value || !searchText.value.trim()) return;
  searching.value = true;
  covers.value = [];
  try {
    const response = await sgdbApi.searchCover({
      searchTerm: searchText.value.trim(),
    });
    covers.value = response.data;
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      `Cover search failed: ${
        e?.response?.data?.detail || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
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

function closeDialog() {
  show.value = false;
  covers.value = [];
  searchText.value = "";
  coverType.value = "all";
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-image-search-outline"
    :width="900"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.search-cover", "Search cover") }}</span>
    </template>

    <template #content>
      <div class="r-v2-sgdb__toolbar">
        <RTextField
          v-model="searchText"
          :placeholder="t('common.search', 'Search')"
          density="comfortable"
          clearable
          hide-details
          class="r-v2-sgdb__search"
          @keyup.enter="doSearch"
        />
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
          :disabled="!searchText.trim()"
          @click="doSearch"
        >
          {{ t("common.search", "Search") }}
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
          :message="t('rom.no-covers-found', 'No covers match this search.')"
        />

        <div v-else-if="hasResults" class="r-v2-sgdb__games">
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
                <img
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
          :message="
            t(
              'rom.search-cover-hint',
              'Type a title and press Enter to search SteamGridDB.',
            )
          "
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

.r-v2-sgdb__games {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-sgdb__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  padding: 12px 16px 16px;
}

.r-v2-sgdb__cover {
  appearance: none;
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
</style>
