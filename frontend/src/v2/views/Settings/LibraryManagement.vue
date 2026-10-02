<script setup lang="ts">
// LibraryManagement: v2-native rewrite. Uses the shared `RTabNav`
// primitive for the underline tabs (same component Game Details uses)
// and keeps the `?tab=` query param so deep links still work.
import { RTabNav, type RTabNavItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import ConfigFileAlerts from "@/v2/components/Settings/ConfigFileAlerts.vue";
import ExcludedSection from "@/v2/components/Settings/ExcludedSection.vue";
import FolderMappingsSection from "@/v2/components/Settings/FolderMappingsSection.vue";
import MissingFirmwareSection from "@/v2/components/Settings/MissingFirmwareSection.vue";
import MissingGamesSection from "@/v2/components/Settings/MissingGamesSection.vue";
import { useRouteQueryParam } from "@/v2/composables/useRouteQueryParam";

const { t } = useI18n();

type Tab = "mapping" | "excluded" | "missing" | "missing-firmware";
const validTabs: readonly Tab[] = [
  "mapping",
  "excluded",
  "missing",
  "missing-firmware",
];

const tab = useRouteQueryParam("tab", "mapping", validTabs);

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
    if ((validTabs as readonly string[]).includes(v)) tab.value = v as Tab;
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
