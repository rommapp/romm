<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import CreateExclusionDialog from "@/components/Settings/LibraryManagement/Dialog/CreateExclusion.vue";
import ExcludedCard from "@/components/Settings/LibraryManagement/ExcludedCard.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import { ref } from "vue";

// Props
const configStore = storeConfig();
const authStore = storeAuth();
const exclusions = [
  {
    set: configStore.config.EXCLUDED_PLATFORMS,
    title: "Platform",
    icon: "mdi-controller-off",
    type: "EXCLUDED_PLATFORMS",
  },
  {
    set: configStore.config.EXCLUDED_SINGLE_FILES,
    title: "Single rom files",
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_SINGLE_FILES",
  },
  {
    set: configStore.config.EXCLUDED_SINGLE_EXT,
    title: "Single Roms Extensions",
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_SINGLE_EXT",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_FILES,
    title: "Multi Roms Files",
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_FILES",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_PARTS_FILES,
    title: "Multi Roms Parts Files",
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_PARTS_FILES",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_PARTS_EXT,
    title: "Multi Roms Parts Extensions",
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_PARTS_EXT",
  },
];
const editable = ref(false);
</script>
<template>
  <r-section icon="mdi-cancel" title="Excluded">
    <template #toolbar-append>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        class="ma-2"
        rounded="0"
        size="small"
        :color="editable ? 'romm-accent-1' : ''"
        variant="text"
        icon="mdi-cog"
        @click="editable = !editable"
      />
    </template>
    <template #content>
      <excluded-card
        v-for="exclusion in exclusions"
        class="mb-1"
        :set="exclusion.set"
        :type="exclusion.type"
        :title="exclusion.title"
        :icon="exclusion.icon"
        :editable="editable && authStore.scopes.includes('platforms.write')"
      />
    </template>
  </r-section>

  <create-exclusion-dialog />
</template>
