<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import type { Platform } from "@/stores/platforms";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

// Props
const { xs } = useDisplay();
const { t } = useI18n();
const romsStore = storeRoms();
const emitter = inject<Emitter<Events>>("emitter");
const searching = ref(false);
const searched = ref(false);
const selectedPlatform = ref<Platform | null>(null);
const galleryFilterStore = storeGalleryFilter();
const { filterPlatforms } = storeToRefs(galleryFilterStore);

// Functions
function setFilters() {
  galleryFilterStore.setFilterGenres([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.genres.map((genre) => genre))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterFranchises([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.franchises.map((franchise) => franchise))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterCompanies([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.companies.map((company) => company))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterCollections([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.collections.map((collection) => collection))
        .sort(),
    ),
  ]);
  galleryFilterStore.setFilterAgeRatings([
    ...new Set(
      romsStore.filteredRoms
        .flatMap((rom) => rom.age_ratings.map((ageRating) => ageRating))
        .sort(),
    ),
  ]);
}

function filterRoms() {
  if (selectedPlatform.value) {
    romsStore.setFiltered(
      romsStore.allRoms.filter(
        (rom) => rom.platform_id === selectedPlatform.value?.id,
      ),
      galleryFilterStore,
    );
  } else {
    romsStore.setFiltered(romsStore.allRoms, galleryFilterStore);
  }
  setFilters();
}

function clearFilter() {
  selectedPlatform.value = null;
  filterRoms();
}
</script>

<template>
  <v-select
    :density="xs ? 'comfortable' : 'default'"
    @click:clear="clearFilter"
    :label="t('common.platform')"
    class="bg-terciary"
    item-title="platform_name"
    :disabled="filterPlatforms.length == 0 || searching"
    hide-details
    rounded="0"
    clearable
    single-line
    return-object
    v-model="selectedPlatform"
    @update:model-value="filterRoms"
    :items="filterPlatforms"
  >
    <template #item="{ props, item }">
      <v-list-item
        class="py-2"
        v-bind="props"
        :title="item.raw.display_name ?? ''"
      >
        <template #prepend>
          <platform-icon
            :size="35"
            :key="item.raw.slug"
            :slug="item.raw.slug"
            :name="item.raw.display_name"
          />
        </template>
      </v-list-item>
    </template>
    <template #selection="{ item }">
      <v-list-item class="px-0" :title="item.raw.display_name ?? ''">
        <template #prepend>
          <platform-icon
            :size="35"
            :key="item.raw.slug"
            :slug="item.raw.slug"
            :name="item.raw.display_name"
          />
        </template>
      </v-list-item>
    </template>
  </v-select>
</template>
