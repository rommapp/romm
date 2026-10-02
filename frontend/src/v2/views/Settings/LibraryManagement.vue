<script setup lang="ts">
// LibraryManagement: v2-native rewrite. Uses the shared `RTabNav`
// primitive for the underline tabs (same component Game Details uses)
// and keeps the `?tab=` query param so deep links still work.
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import ConfigFileAlerts from "@/v2/components/Settings/ConfigFileAlerts.vue";
import ExcludedSection from "@/v2/components/Settings/ExcludedSection.vue";
import FolderMappingsSection from "@/v2/components/Settings/FolderMappingsSection.vue";
import MissingFirmwareSection from "@/v2/components/Settings/MissingFirmwareSection.vue";
import MissingGamesSection from "@/v2/components/Settings/MissingGamesSection.vue";
import { syncQueryParam } from "@/v2/utils/routeQuery";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

type Tab = "mapping" | "excluded" | "missing" | "missing-firmware";
const validTabs: Tab[] = ["mapping", "excluded", "missing", "missing-firmware"];

const tab = ref<Tab>(
  (validTabs as string[]).includes(route.query.tab as string)
    ? (route.query.tab as Tab)
    : "mapping",
);

watch(tab, (newTab) => syncQueryParam(router, "tab", newTab));

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
  {
    id: "missing-firmware",
    label: t("settings.missing-firmware-tab"),
    icon: "mdi-memory",
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
  <div class="r-v2-section-stack">
    <ConfigFileAlerts />

    <RTabNav v-model="tabModel" :items="tabs" />

    <FolderMappingsSection v-if="tab === 'mapping'" />
    <ExcludedSection v-else-if="tab === 'excluded'" />
    <MissingGamesSection v-else-if="tab === 'missing'" />
    <MissingFirmwareSection v-else-if="tab === 'missing-firmware'" />
  </div>
</template>
