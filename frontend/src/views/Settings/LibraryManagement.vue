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
const romsStore = storeRoms();
const { fetchingRoms, fetchTotalRoms, filteredRoms } = storeToRefs(romsStore);
const galleryViewStore = storeGalleryView();
const { scrolledToTop } = storeToRefs(galleryViewStore);
const galleryFilterStore = storeGalleryFilter();
const { selectedPlatform } = storeToRefs(galleryFilterStore);
const platformsStore = storePlatforms();
const missingGamesLoading = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
let timeout: ReturnType<typeof setTimeout> = setTimeout(() => {}, 400);
const allPlatforms = computed(() =>
  [
    ...new Map(
      filteredRoms.value
        .map((rom) => platformsStore.get(rom.platform_id))
        .filter((platform) => !!platform)
        .map((platform) => [platform!.id, platform]),
    ).values(),
  ].sort((a, b) => a!.name.localeCompare(b!.name)),
);

const onFilterChange = debounce(
  () => {
    romsStore.resetPagination();
    galleryFilterStore.setFilterMissing(true);
    romsStore.fetchRoms({
      galleryFilter: galleryFilterStore,
      concat: false,
    });

    const url = new URL(window.location.href);
    // Update URL with filters
    Object.entries({
      platform: selectedPlatform.value
        ? String(selectedPlatform.value.id)
        : null,
    }).forEach(([key, value]) => {
      if (value) {
        url.searchParams.set(key, value);
      } else {
        url.searchParams.delete(key);
      }
    });
    galleryFilterStore.setFilterMissing(false);
  },
  500,
  // If leading and trailing options are true, this is invoked on the trailing edge of
  // the timeout only if the the function is invoked more than once during the wait
  { leading: false, trailing: true },
);

async function fetchRoms() {
  if (fetchingRoms.value) return;

  emitter?.emit("showLoadingDialog", {
    loading: true,
    scrim: false,
  });

  galleryFilterStore.setFilterMissing(true);
  romsStore
    .fetchRoms({ galleryFilter: galleryFilterStore })
    .then(() => {
      emitter?.emit("showLoadingDialog", {
        loading: false,
        scrim: false,
      });
    })
    .catch((error) => {
      console.error("Error fetching missing games:", error);
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch missing ROMs: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      galleryFilterStore.setFilterMissing(false);
      if (romsStore.fetchOffset === romsStore.fetchLimit) {
        missingGamesLoading.value = false;
      }
    });
}

function cleanupAll() {
  romsStore.setLimit(MAX_FETCH_LIMIT);
  galleryFilterStore.setFilterMissing(true);
  romsStore
    .fetchRoms({ galleryFilter: galleryFilterStore })
    .then(() => {
      emitter?.emit("showLoadingDialog", {
        loading: false,
        scrim: false,
      });
      if (filteredRoms.value.length > 0) {
        emitter?.emit("showDeleteRomDialog", filteredRoms.value);
      } else {
        emitter?.emit("snackbarShow", {
          msg: "No missing ROMs to delete",
          icon: "mdi-close-circle",
          color: "red",
          timeout: 4000,
        });
      }
    })
    .catch((error) => {
      console.error("Error fetching missing games:", error);
      emitter?.emit("snackbarShow", {
        msg: `Couldn't fetch missing ROMs: ${error}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      galleryFilterStore.setFilterMissing(false);
    });
}

function resetMissingRoms() {
  romsStore.reset();
  galleryFilterStore.resetFilters();
}

const { y: windowY } = useScroll(window, { throttle: 500 });

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
    if (newTab && validTabs.includes(newTab as any) && tab.value !== newTab) {
      tab.value = newTab as "mapping" | "excluded" | "missing";
    }
  },
  { immediate: true },
);

watch(windowY, () => {
  clearTimeout(timeout);

  window.setTimeout(async () => {
    scrolledToTop.value = windowY.value === 0;
    if (
      windowY.value + window.innerHeight >= document.body.scrollHeight - 300 &&
      fetchTotalRoms.value > filteredRoms.value.length
    ) {
      await fetchRoms();
    }
  }, 100);
});

onMounted(() => {
  resetMissingRoms();
  // Only fetch ROMs if we're on the missing tab
  if (tab.value === "missing") {
    fetchRoms();
  }
});

onUnmounted(() => {
  resetMissingRoms();
});
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
        <v-tab prepend-icon="mdi-folder-cog" class="rounded" value="mapping">
          {{ t("settings.folder-mappings") }}
        </v-tab>
        <v-tab prepend-icon="mdi-cancel" class="rounded" value="excluded">
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
