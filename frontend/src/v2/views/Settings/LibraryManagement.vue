<script setup lang="ts">
// LibraryManagement — v2-native rewrite. Uses the shared `RTabNav`
// primitive for the underline tabs (same component Game Details uses)
// and keeps the `?tab=` query param so deep links still work.
import { RAlert, RTabNav, type RTabNavItem } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import storeConfig from "@/stores/config";
import ExcludedSection from "@/v2/components/Settings/ExcludedSection.vue";
import FolderMappingsSection from "@/v2/components/Settings/FolderMappingsSection.vue";
import MissingGamesSection from "@/v2/components/Settings/MissingGamesSection.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

type Tab = "mapping" | "excluded" | "missing";
const validTabs: Tab[] = ["mapping", "excluded", "missing"];

const tab = ref<Tab>(
  (validTabs as string[]).includes(route.query.tab as string)
    ? (route.query.tab as Tab)
    : "mapping",
);
const configStore = storeConfig();
const { config } = storeToRefs(configStore);

watch(tab, (newTab) => {
  router.replace({
    path: route.path,
    query: { ...route.query, tab: newTab },
  });
});

watch(
  () => route.query.tab,
  (newTab) => {
    if (
      newTab &&
      (validTabs as string[]).includes(newTab as string) &&
      tab.value !== newTab
    ) {
      tab.value = newTab as Tab;
    }
  },
  { immediate: true },
);

const tabs = computed<RTabNavItem[]>(() => [
  {
    id: "mapping",
    label: t("settings.folder-mappings"),
    icon: "mdi-folder-multiple-outline",
  },
  {
    id: "excluded",
    label: t("settings.excluded"),
    icon: "mdi-eye-off-outline",
  },
  {
    id: "missing",
    label: t("settings.missing-games-tab"),
    icon: "mdi-folder-question-outline",
  },
]);

// Bridge between RTabNav's string modelValue and our Tab union.
const tabModel = computed<string>({
  get: () => tab.value,
  set: (v) => {
    if ((validTabs as string[]).includes(v)) tab.value = v as Tab;
  },
});
</script>

<template>
  <div>
    <RAlert v-if="!config.CONFIG_FILE_MOUNTED" type="error">
      <template #title>
        {{ t("settings.config-file-not-mounted-title") }}
      </template>
      {{ t("settings.config-file-not-mounted-desc") }}
    </RAlert>
    <RAlert v-else-if="!config.CONFIG_FILE_WRITABLE" type="warning">
      <template #title>
        {{ t("settings.config-file-not-writable-title") }}
      </template>
      {{ t("settings.config-file-not-writable-desc") }}
    </RAlert>

    <RTabNav v-model="tabModel" :items="tabs" class="r-v2-lib__tabs" />

    <FolderMappingsSection v-if="tab === 'mapping'" />
    <ExcludedSection v-else-if="tab === 'excluded'" />
    <MissingGamesSection v-else-if="tab === 'missing'" />
  </div>
</template>

<style scoped>
.r-v2-lib__tabs {
  margin-bottom: 20px;
}
</style>
