<script setup lang="ts">
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { searchTerm } = storeToRefs(galleryFilterStore);

const isFiltered = computed(() => galleryFilterStore.isFiltered());
const emitter = inject<Emitter<Events>>("emitter");

function openCreateDialog() {
  emitter?.emit("showCreateSmartCollectionDialog", null);
}
</script>

<template>
  <v-btn
    v-if="isFiltered || searchTerm"
    icon="mdi-playlist-plus"
    @click="openCreateDialog"
    variant="text"
    :title="t('collection.add-collection')"
    color="primary"
  />
</template>
