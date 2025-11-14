<script setup lang="ts">
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import CreateExclusionDialog from "@/components/Settings/LibraryManagement/Config/Dialog/CreateExclusion.vue";
import ExcludedCard from "@/components/Settings/LibraryManagement/Config/ExcludedCard.vue";
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";

const { t } = useI18n();
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
const authStore = storeAuth();
const exclusions = [
  {
    set: config.value.EXCLUDED_PLATFORMS,
    title: t("common.platform"),
    icon: "mdi-controller-off",
    type: "EXCLUDED_PLATFORMS",
  },
  {
    set: config.value.EXCLUDED_SINGLE_FILES,
    title: t("settings.excluded-single-rom-files"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_SINGLE_FILES",
  },
  {
    set: config.value.EXCLUDED_SINGLE_EXT,
    title: t("settings.excluded-single-rom-extensions"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_SINGLE_EXT",
  },
  {
    set: config.value.EXCLUDED_MULTI_FILES,
    title: t("settings.excluded-multi-rom-files"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_FILES",
  },
  {
    set: config.value.EXCLUDED_MULTI_PARTS_FILES,
    title: t("settings.excluded-multi-rom-parts-files"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_PARTS_FILES",
  },
  {
    set: config.value.EXCLUDED_MULTI_PARTS_EXT,
    title: t("settings.excluded-multi-rom-parts-extensions"),
    icon: "mdi-file-document-remove-outline",
    type: "EXCLUDED_MULTI_PARTS_EXT",
  },
];
const editable = ref(false);
</script>
<template>
  <RSection icon="mdi-cancel" :title="t('settings.excluded')">
    <template #toolbar-append>
      <v-btn
        v-if="authStore.scopes.includes('platforms.write')"
        class="ma-2"
        size="small"
        :color="editable ? 'primary' : ''"
        variant="text"
        icon="mdi-cog"
        @click="editable = !editable"
        :disabled="!config.CONFIG_FILE_WRITABLE"
      />
    </template>
    <template #content>
      <ExcludedCard
        v-for="exclusion in exclusions"
        :key="exclusion.type"
        class="mb-1"
        :set="exclusion.set"
        :type="exclusion.type"
        :title="exclusion.title"
        :icon="exclusion.icon"
        :editable="editable && authStore.scopes.includes('platforms.write')"
      />
      <CreateExclusionDialog />
    </template>
  </RSection>
</template>
