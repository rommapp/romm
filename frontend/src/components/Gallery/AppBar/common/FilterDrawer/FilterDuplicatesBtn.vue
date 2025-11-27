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
const { filterDuplicates } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Computed property to determine current state
const currentState = computed(() => {
  if (filterDuplicates.value === true) return "duplicates";
  if (filterDuplicates.value === false) return "not-duplicates";
  return "all"; // null
});

// Handler for state changes
function setState(state: string | null) {
  if (!state) return;

  galleryFilterStore.setFilterDuplicatesState(
    state as "all" | "duplicates" | "not-duplicates",
  );
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
        mdi-card-multiple
      </v-icon>
      <span
        :class="
          currentState !== 'all'
            ? 'text-primary font-weight-medium'
            : 'text-medium-emphasis'
        "
        class="text-body-1"
      >
        {{ t("platform.show-duplicates") }}
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
      <v-tooltip text="Show duplicate ROMs only" location="bottom">
        <template #activator="{ props }">
          <v-btn
            value="duplicates"
            size="small"
            v-bind="props"
            :disabled="fetchTotalRoms > 10000"
          >
            <v-icon size="x-large">mdi-card-multiple</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
      <v-tooltip text="Show non-duplicate ROMs only" location="bottom">
        <template #activator="{ props }">
          <v-btn
            value="not-duplicates"
            size="small"
            v-bind="props"
            :disabled="fetchTotalRoms > 10000"
          >
            <v-icon size="x-large">mdi-card-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
    </v-btn-toggle>
  </div>
</template>
