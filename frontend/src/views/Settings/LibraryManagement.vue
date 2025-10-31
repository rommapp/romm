<script setup lang="ts">
import { useScroll } from "@vueuse/core";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { ref, onMounted, inject, onUnmounted, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import LoadMoreBtn from "@/components/Gallery/LoadMoreBtn.vue";
import Excluded from "@/components/Settings/LibraryManagement/Config/Excluded.vue";
import PlatformBinding from "@/components/Settings/LibraryManagement/Config/PlatformBinding.vue";
import PlatformVersions from "@/components/Settings/LibraryManagement/Config/PlatformVersions.vue";
import GameTable from "@/components/common/Game/VirtualTable.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import storeConfig from "@/stores/config";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";
import storeRoms, { MAX_FETCH_LIMIT } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const tab = ref<"config" | "missing">("config");
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

const { y: documentY } = useScroll(document.body, { throttle: 500 });

watch(documentY, () => {
  clearTimeout(timeout);

  window.setTimeout(async () => {
    scrolledToTop.value = documentY.value === 0;
    if (
      documentY.value + window.innerHeight >=
        document.body.scrollHeight - 300 &&
      fetchTotalRoms.value > filteredRoms.value.length
    ) {
      await fetchRoms();
    }
  }, 100);
});

onMounted(() => {
  resetMissingRoms();
  fetchRoms();
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
        <v-tab prepend-icon="mdi-cog" class="rounded" value="config">
          Config
        </v-tab>
        <v-tab
          prepend-icon="mdi-folder-question"
          class="rounded"
          value="missing"
        >
          Missing games
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
        <template #title>Configuration file not mounted!</template>
        <template #text>
          The config.yml file has not been mounted. Any changes made to the
          configuration will not persist after the application restarts.
        </template>
      </v-alert>
      <v-alert
        v-else-if="!config.CONFIG_FILE_WRITABLE"
        type="warning"
        variant="tonal"
        class="my-2"
      >
        <template #title>Configuration file not writable!</template>
        <template #text>
          The config.yml file is not writable. Any changes made to the
          configuration will not persist after the application restarts.
        </template>
      </v-alert>
      <v-tabs-window v-model="tab">
        <v-tabs-window-item value="config">
          <PlatformBinding class="mt-2" />
          <PlatformVersions class="mt-4" />
          <Excluded class="mt-4" />
        </v-tabs-window-item>
        <v-tabs-window-item value="missing">
          <v-row class="mt-2 mr-2 align-center" no-gutters>
            <v-col>
              <v-select
                v-model="selectedPlatform"
                class="mx-2"
                hide-details
                prepend-inner-icon="mdi-controller"
                clearable
                :label="t('common.platform')"
                variant="outlined"
                density="comfortable"
                :items="allPlatforms"
                @update:model-value="onFilterChange"
              >
                <template #item="{ props, item }">
                  <v-list-item
                    v-bind="props"
                    class="py-4"
                    :title="item.raw.name ?? ''"
                    :subtitle="item.raw.fs_slug"
                  >
                    <template #prepend>
                      <PlatformIcon
                        :key="item.raw.slug"
                        :size="35"
                        :slug="item.raw.slug"
                        :name="item.raw.name"
                        :fs-slug="item.raw.fs_slug"
                      />
                    </template>
                    <template #append>
                      <MissingFromFSIcon
                        v-if="item.raw.missing_from_fs"
                        text="Missing platform from filesystem"
                        chip
                        chip-label
                        chip-density="compact"
                        class="ml-2"
                      />
                      <v-chip class="ml-2" size="x-small" label>
                        {{ item.raw.rom_count }}
                      </v-chip>
                    </template>
                  </v-list-item>
                </template>
                <template #chip="{ item }">
                  <PlatformIcon
                    :key="item.raw.slug"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                    :fs-slug="item.raw.fs_slug"
                    :size="20"
                    class="mx-2"
                  />
                  {{ item.raw.name }}
                </template>
              </v-select>
            </v-col>
            <v-col cols="auto">
              <v-btn
                prepend-icon="mdi-delete"
                size="large"
                class="text-romm-red bg-toplayer"
                variant="flat"
                @click="cleanupAll"
              >
                Clean up all
              </v-btn>
            </v-col>
          </v-row>
          <GameTable class="mx-2 mt-2" show-platform-icon />
          <LoadMoreBtn :fetch-roms="fetchRoms" />
          <FabOverlay />
        </v-tabs-window-item>
      </v-tabs-window>
    </v-col>
  </v-row>
</template>
