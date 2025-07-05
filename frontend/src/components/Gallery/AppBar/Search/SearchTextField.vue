<script setup lang="ts">
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, nextTick, onMounted, watch } from "vue";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const router = useRouter();
const romsStore = storeRoms();
const { initialSearch } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);

async function fetchRoms() {
  if (searchTerm.value === null) return;
  initialSearch.value = true;
  emitter?.emit("filterRoms", null);
}

function clearInput() {
  searchTerm.value = null;
}

function resetGallery() {
  romsStore.setCurrentPlatform(null);
  romsStore.setCurrentCollection(null);
  romsStore.reset();
  galleryFilterStore.resetFilters();
  galleryFilterStore.activeFilterDrawer = false;
}

onMounted(() => resetGallery());

watch(
  () => router.currentRoute.value.query,
  (query) => {
    if (query.search !== undefined && query.search !== searchTerm.value) {
      searchTerm.value = query.search as string;
      fetchRoms();
    }
  },
  { deep: true },
);
</script>

<template>
  <v-text-field
    density="default"
    clearable
    autofocus
    hide-details
    rounded="0"
    :label="t('common.search')"
    v-model="searchTerm"
    @keyup.enter="fetchRoms"
    @click:clear="clearInput"
    @update:model-value="nextTick(fetchRoms)"
  />
</template>
