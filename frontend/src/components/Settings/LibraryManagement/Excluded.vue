<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import CreateExclusionDialog from "@/components/Settings/LibraryManagement/Dialog/CreateExclusion.vue";
import ExcludedCard from "@/components/Settings/LibraryManagement/ExcludedCard.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import { ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const configStore = storeConfig();
const authStore = storeAuth();
const exclusions = [
  {
    set: configStore.config.EXCLUDED_PLATFORMS,
    title: t("common.platform"),
    icon: "mdi-controller-off",
    type: "EXCLUDED_PLATFORMS",
  },
  {
    set: configStore.config.EXCLUDED_SINGLE_FILES,
    title: t("settings.excluded-single-rom-files"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_SINGLE_FILES",
  },
  {
    set: configStore.config.EXCLUDED_SINGLE_EXT,
    title: t("settings.excluded-single-rom-extensions"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_SINGLE_EXT",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_FILES,
    title: t("settings.excluded-multi-rom-files"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_FILES",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_PARTS_FILES,
    title: t("settings.excluded-multi-rom-parts-files"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_PARTS_FILES",
  },
  {
    set: configStore.config.EXCLUDED_MULTI_PARTS_EXT,
    title: t("settings.excluded-multi-rom-parts-extensions"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_PARTS_EXT",
  },
];
const editable = ref(false);
</script>
<template>
  <r-section icon="mdi-cancel" :title="t('settings.excluded')">
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
