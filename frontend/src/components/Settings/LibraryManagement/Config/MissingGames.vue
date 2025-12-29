<script setup lang="ts">
import { useScroll } from "@vueuse/core";
import { debounce } from "lodash";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onMounted, onUnmounted, computed, watch } from "vue";
import { useI18n } from "vue-i18n";
import FabOverlay from "@/components/Gallery/FabOverlay.vue";
import LoadMoreBtn from "@/components/Gallery/LoadMoreBtn.vue";
import GameTable from "@/components/common/Game/VirtualTable.vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeGalleryView from "@/stores/galleryView";
import storePlatforms from "@/stores/platforms";
import storeRoms, { MAX_FETCH_LIMIT } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const romsStore = storeRoms();
const { fetchingRoms, fetchTotalRoms, filteredRoms } = storeToRefs(romsStore);
const galleryViewStore = storeGalleryView();
const { scrolledToTop } = storeToRefs(galleryViewStore);
const galleryFilterStore = storeGalleryFilter();
const { selectedPlatform } = storeToRefs(galleryFilterStore);
const platformsStore = storePlatforms();
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
        msg: t("settings.couldnt-fetch-missing-roms", { error }),
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    })
    .finally(() => {
      galleryFilterStore.setFilterMissing(false);
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
          msg: t("settings.no-missing-roms-to-delete"),
          icon: "mdi-close-circle",
          color: "red",
          timeout: 4000,
        });
      }
    })
    .catch((error) => {
      console.error("Error fetching missing games:", error);
      emitter?.emit("snackbarShow", {
        msg: t("settings.couldnt-fetch-missing-roms", { error }),
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
  <div v-if="filteredRoms.length === 0" class="text-center py-8">
    <v-icon icon="mdi-folder-question" size="48" class="mb-2 opacity-50" />
    <div class="text-body-2 text-romm-gray">
      {{ t("settings.missing-games-none") }}
    </div>
  </div>
  <template v-else>
    <v-row class="align-center" no-gutters>
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
                  :text="t('settings.missing-platform-from-fs')"
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
          {{ t("settings.cleanup-all") }}
        </v-btn>
      </v-col>
    </v-row>
    <GameTable class="mx-2 mt-2" show-platform-icon />
    <LoadMoreBtn :fetch-roms="fetchRoms" />
    <FabOverlay />
  </template>
</template>
