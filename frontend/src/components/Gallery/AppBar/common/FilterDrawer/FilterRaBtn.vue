<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const romsStore = storeRoms();
const galleryFilterStore = storeGalleryFilter();
const { fetchTotalRoms } = storeToRefs(romsStore);
const { filterRA } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Computed property to determine current state
const currentState = computed(() => {
  if (filterRA.value === true) return "has-ra";
  if (filterRA.value === false) return "no-ra";
  return "all"; // null
});

// Handler for state changes
function setState(state: string | null) {
  if (!state) return;

  galleryFilterStore.setFilterRAState(state as "all" | "has-ra" | "no-ra");
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <div
    class="d-flex align-center justify-space-between py-2 px-4 rounded-lg border"
    :class="{ 'opacity-50': fetchTotalRoms > 10000 }"
  >
    <div class="d-flex align-center">
      <v-icon
        :color="currentState !== 'all' ? 'primary' : 'grey-lighten-1'"
        class="mr-3"
      >
        mdi-trophy
      </v-icon>
      <span
        :class="
          currentState !== 'all'
            ? 'text-primary font-weight-medium'
            : 'text-medium-emphasis'
        "
        class="text-body-1"
      >
        {{ t("platform.show-ra") }}
      </span>
    </div>
    <v-btn-toggle
      :model-value="currentState"
      color="primary"
      density="compact"
      variant="outlined"
      :disabled="fetchTotalRoms > 10000"
      @update:model-value="setState"
    >
      <v-btn value="all" size="small">All</v-btn>
      <v-tooltip text="Show ROMs with RetroAchievements only" location="bottom">
        <template #activator="{ props }">
          <v-btn
            value="has-ra"
            size="small"
            v-bind="props"
            :disabled="fetchTotalRoms > 10000"
          >
            <v-icon size="x-large">mdi-trophy</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
      <v-tooltip
        text="Show ROMs without RetroAchievements only"
        location="bottom"
      >
        <template #activator="{ props }">
          <v-btn
            value="no-ra"
            size="small"
            v-bind="props"
            :disabled="fetchTotalRoms > 10000"
          >
            <v-icon size="x-large">mdi-trophy-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
    </v-btn-toggle>
  </div>
</template>
