<script setup lang="ts">
import { storeToRefs } from "pinia";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import Excluded from "@/components/Settings/LibraryManagement/Config/Excluded.vue";
import FolderMappings from "@/components/Settings/LibraryManagement/Config/FolderMappings.vue";
import MissingGames from "@/components/Settings/LibraryManagement/Config/MissingGames.vue";
import storeConfig from "@/stores/config";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

// Valid tab values
const validTabs = ["mapping", "excluded", "missing"] as const;

// Initialize tab from query parameter or default to "config"
const tab = ref<"mapping" | "excluded" | "missing">(
    validTabs.includes(route.query.tab as any)
        ? (route.query.tab as "mapping" | "excluded" | "missing")
        : "mapping",
);
const configStore = storeConfig();
const { config } = storeToRefs(configStore);
// Watch for tab changes and update URL
watch(tab, (newTab) => {
    router.replace({
        path: route.path,
        query: {
            ...route.query,
            tab: newTab,
        },
    });
});

// Watch for URL changes and update tab
watch(
    () => route.query.tab,
    (newTab) => {
        if (
            newTab &&
            validTabs.includes(newTab as any) &&
            tab.value !== newTab
        ) {
            tab.value = newTab as "mapping" | "excluded" | "missing";
        }
    },
    { immediate: true },
);
</script>

<template>
    <v-row no-gutters class="pa-2">
        <v-col cols="12">
            <v-tabs
                v-model="tab"
                align-tabs="start"
                slider-color="secondary"
                selected-class="bg-toplayer"
            >
                <v-tab
                    prepend-icon="mdi-folder-cog"
                    class="rounded"
                    value="mapping"
                >
                    {{ t("settings.folder-mappings") }}
                </v-tab>
                <v-tab
                    prepend-icon="mdi-cancel"
                    class="rounded"
                    value="excluded"
                >
                    {{ t("settings.excluded") }}
                </v-tab>
                <v-tab
                    prepend-icon="mdi-folder-question"
                    class="rounded"
                    value="missing"
                >
                    {{ t("settings.missing-games-tab") }}
                </v-tab>
            </v-tabs>
        </v-col>
        <v-col>
            <v-alert
                v-if="!config.CONFIG_FILE_MOUNTED"
                type="error"
                variant="tonal"
                class="my-2"
            >
                <template #title>{{
                    t("settings.config-file-not-mounted-title")
                }}</template>
                <template #text>
                    {{ t("settings.config-file-not-mounted-desc") }}
                </template>
            </v-alert>
            <v-alert
                v-else-if="!config.CONFIG_FILE_WRITABLE"
                type="warning"
                variant="tonal"
                class="my-2"
            >
                <template #title>{{
                    t("settings.config-file-not-writable-title")
                }}</template>
                <template #text>
                    {{ t("settings.config-file-not-writable-desc") }}
                </template>
            </v-alert>
            <v-tabs-window v-model="tab">
                <v-tabs-window-item value="mapping">
                    <FolderMappings />
                </v-tabs-window-item>
                <v-tabs-window-item value="excluded">
                    <Excluded />
                </v-tabs-window-item>
                <v-tabs-window-item value="missing">
                    <MissingGames />
                </v-tabs-window-item>
            </v-tabs-window>
        </v-col>
    </v-row>
</template>
