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
const { searchTerm } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

const filterRoms = debounce(() => {
  // Update URL with search term
  router.replace({ query: { search: searchTerm.value } });
  emitter?.emit("filter", null);
}, 500);

function clear() {
  searchTerm.value = null;
}

onMounted(() => {
  const { search } = router.currentRoute.value.query;
  if (search !== undefined && search !== searchTerm.value) {
    searchTerm.value = search as string;
    filterRoms();
  }
});

watch(
  () => router.currentRoute.value.query,
  (query) => {
    if (query.search !== undefined && query.search !== searchTerm.value) {
      searchTerm.value = query.search as string;
      filterRoms();
    }
  },
  { deep: true },
);
</script>

<template>
  <v-text-field
    v-model="searchTerm"
    prepend-inner-icon="mdi-filter-outline"
    :label="t('common.filter')"
    hide-details
    rounded="0"
    clearable
    @click:clear="clear"
    @update:model-value="nextTick(filterRoms)"
  />
</template>
