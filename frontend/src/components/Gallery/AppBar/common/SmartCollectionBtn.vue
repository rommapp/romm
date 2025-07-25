<script setup lang="ts">
import { computed, inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();

const isFiltered = computed(() => galleryFilterStore.isFiltered());
const emitter = inject<Emitter<Events>>("emitter");

function openCreateDialog() {
  emitter?.emit("showCreateSmartCollectionDialog", null);
}
</script>

<template>
  <v-btn
    v-if="isFiltered"
    icon="mdi-playlist-plus"
    @click="openCreateDialog"
    variant="text"
    :title="t('collection.add-collection')"
    color="primary"
  />
</template>
