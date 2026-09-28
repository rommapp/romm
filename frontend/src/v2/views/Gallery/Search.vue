<script setup lang="ts">
// Search — global ROM search. Thin orchestrator: clears any prior
// gallery scope, kicks the initial fetch, and fills the shell's
// `#header` slot with a PageHeader. Everything else lives in
// `GalleryShell`.
import { RTag } from "@v2/lib";
import { storeToRefs } from "pinia";
import { nextTick, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import GalleryShell from "@/v2/components/Gallery/GalleryShell.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

const { t } = useI18n();
const galleryRoms = storeGalleryRoms();
const { total, initialFetching } = storeToRefs(galleryRoms);

const initialSearch = ref(false);
const shellRef = ref<InstanceType<typeof GalleryShell> | null>(null);

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
    autofocus-search
    :empty-message="t('rom.no-games-match')"
    empty-icon="mdi-magnify-close"
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
  </GalleryShell>
</template>
