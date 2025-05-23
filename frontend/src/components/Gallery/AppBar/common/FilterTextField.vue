<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";

// Props
const { t } = useI18n();
const { xs } = useDisplay();
const router = useRouter();
const galleryFilterStore = storeGalleryFilter();
const romsStore = storeRoms();
const { searchTerm } = storeToRefs(galleryFilterStore);
const { fetchingRoms } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");

const filterRoms = debounce(() => {
  // Update URL with search term
  router.replace({ query: { search: searchTerm.value } });
  emitter?.emit("filter", null);
}, 500);

function clearInput() {
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
    :density="xs ? 'comfortable' : 'default'"
    clearable
    hide-details
    rounded="0"
    :label="t('common.filter')"
    v-model="searchTerm"
    :disabled="fetchingRoms"
    @keyup.enter="filterRoms"
    prepend-inner-icon="mdi-filter-outline"
    @click:clear="clearInput"
    @update:model-value="nextTick(filterRoms)"
  />
</template>
