<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const router = useRouter();
const galleryFilterStore = storeGalleryFilter();
const { searchText } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

const filterRoms = debounce(() => {
  // Update URL with search term
  router.replace({ query: { search: searchText.value } });
  emitter?.emit("filter", null);
}, 500);

function clear() {
  searchText.value = null;
}

onMounted(() => {
  const { search: searchTerm } = router.currentRoute.value.query;
  if (searchTerm !== undefined && searchTerm !== searchText.value) {
    searchText.value = searchTerm as string;
    filterRoms();
  }
});

watch(
  () => router.currentRoute.value.query,
  (query) => {
    if (query.search !== undefined && query.search !== searchText.value) {
      searchText.value = query.search as string;
      filterRoms();
    }
  },
  { deep: true },
);
</script>

<template>
  <v-text-field
    v-model="searchText"
    prepend-inner-icon="mdi-filter-outline"
    :label="t('common.filter')"
    hide-details
    rounded="0"
    clearable
    @click:clear="clear"
    @update:model-value="nextTick(filterRoms)"
  />
</template>
