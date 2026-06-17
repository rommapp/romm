<script setup lang="ts">
// Search — global ROM search. Thin orchestrator: clears any prior
// gallery scope, kicks the initial fetch, and fills the shell's
// `#header` slot with a PageHeader. Everything else lives in
// `GalleryShell`.
import { RTag } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, nextTick, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

const { t } = useI18n();
const galleryRoms = storeGalleryRoms();
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);
const { total, initialFetching } = storeToRefs(galleryRoms);

const initialSearch = ref(false);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);

const showStandaloneEmpty = computed(
  () => !initialFetching.value && total.value === 0 && !!searchTerm.value,
);

const emptyMessage = computed(() =>
  searchTerm.value
    ? t("rom.no-games-match-query", { query: searchTerm.value })
    : t("rom.no-games-match"),
);

onMounted(async () => {
  // Global search — drop ALL gallery scoping from previous views, then
  // flag the gallery as "currently in a search context" so the store's
  // `onGalleryView` getter resolves true and `groupByMetaId` honours
  // the user's `groupRoms` preference. Without this the search results
  // never collapse siblings, even with grouping enabled.
  //
  // Bootstrap metadata only; both grid and list mode hydrate rows via
  // the per-position fetch path (grid: shell viewport-sync; list:
  // GameListRow's onMounted). No big initial batch.
  galleryRoms.resetGallery();
  galleryRoms.currentSearch = true;
  await galleryRoms.fetchInitialMetadata();
  initialSearch.value = true;
  await nextTick();
  shellRef.value?.applyRestoredScroll();
});
</script>

<template>
  <GalleryShell
    ref="shellRef"
    :has-header="true"
    :search-placeholder="t('rom.search-placeholder')"
    :empty-message="emptyMessage"
    :skeleton-row-count="4"
  >
    <!-- HEADER (Section 1) — title + result-count chip. The shell
         auto-measures this slot; no need to declare a height. -->
    <template #header>
      <PageHeader :title="t('common.search')">
        <template #count>
          <RTag v-if="initialSearch && !initialFetching" :text="total" />
        </template>
      </PageHeader>
    </template>

    <!-- EMPTY STATE — boxed illustration when a search resolves with
         no hits. Falls back to the shell's plain text otherwise (e.g.
         before the user types). -->
    <template #empty="{ message }">
      <EmptyState
        v-if="showStandaloneEmpty"
        variant="boxed"
        icon="mdi-emoticon-confused-outline"
        :message="message"
      />
      <span v-else>{{ message }}</span>
    </template>
  </GalleryShell>
</template>
