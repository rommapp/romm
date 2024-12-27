<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const galleryFilterStore = storeGalleryFilter();
const { filterText } = storeToRefs(galleryFilterStore);

const filterRoms = debounce(() => {
  emitter?.emit("filter", null);
}, 500);

function clear() {
  filterText.value = "";
}
</script>

<template>
  <v-text-field
    v-model="filterText"
    prepend-inner-icon="mdi-filter-outline"
    :label="t('common.filter')"
    rounded="0"
    hide-details
    clearable
    @click:clear="clear"
    @update:model-value="nextTick(filterRoms)"
  />
</template>
