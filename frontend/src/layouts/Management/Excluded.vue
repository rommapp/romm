<script setup lang="ts">
import ExcludedCard from "@/components/Management/ExcludedCard.vue";
import RSection from "@/components/common/RSection.vue";
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
    emit: "platform",
  },
  {
    set: configStore.config.EXCLUDED_SINGLE_FILES,
    title: "Single rom files",
    icon: "mdi-file-document-remove-outline",
    emit: "singleFile",
  },
  {
    set: configStore.config.EXCLUDED_SINGLE_EXT,
    title: "Single Roms Extensions",
    icon: "mdi-file-document-remove-outline",
    emit: "singleFileExt",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_FILES,
    title: "Multi Roms Files",
    icon: "mdi-file-document-remove-outline",
    emit: "multiFile",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_PARTS_FILES,
    title: "Multi Roms Parts Files",
    icon: "mdi-file-document-remove-outline",
    emit: "multiFilePart",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_PARTS_EXT,
    title: "Multi Roms Parts Extensions",
    icon: "mdi-file-document-remove-outline",
    emit: "multiFilePartExt",
  },
];
const editable = ref(false);
</script>
<template>
  <r-section icon="mdi-cancel" title="Excluded">
    <template #toolbar-append>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        disabled
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
        :emit="exclusion.emit"
        :title="exclusion.title"
        :icon="exclusion.icon"
        :editable="editable && authStore.scopes.includes('platforms.write')"
      />
    </template>
  </r-section>
</template>
