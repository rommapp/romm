<script setup lang="ts">
import { ref, computed } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import CreateSmartCollectionDialog from "@/components/common/SmartCollection/CreateSmartCollectionDialog.vue";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();

const isFiltered = computed(() => galleryFilterStore.isFiltered());
const createDialog = ref<InstanceType<typeof CreateSmartCollectionDialog>>();

function openCreateDialog() {
  createDialog.value?.openDialog();
}
</script>

<template>
  <v-btn
    v-if="isFiltered"
    icon="mdi-playlist-plus"
    @click="openCreateDialog"
    variant="text"
    :title="t('smartCollection.create', 'Create Smart Collection')"
    color="primary"
  />

  <create-smart-collection-dialog ref="createDialog" />
</template>
