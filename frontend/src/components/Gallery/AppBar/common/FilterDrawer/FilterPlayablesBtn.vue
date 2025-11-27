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
const { filterPlayables } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Computed property to determine current state
const currentState = computed(() => {
  if (filterPlayables.value === true) return "playables";
  if (filterPlayables.value === false) return "not-playables";
  return "all"; // null
});

// Handler for state changes
function setState(state: string | null) {
  if (!state) return;

  galleryFilterStore.setFilterPlayablesState(
    state as "all" | "playables" | "not-playables",
  );
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <div
    class="d-flex align-center justify-space-between py-2"
    :class="{ 'opacity-50': fetchTotalRoms > 10000 }"
  >
    <div class="d-flex align-center">
      <v-icon
        :color="currentState !== 'all' ? 'primary' : 'grey-lighten-1'"
        class="mr-3"
      >
        mdi-play
      </v-icon>
      <span
        :class="
          currentState !== 'all'
            ? 'text-primary font-weight-medium'
            : 'text-medium-emphasis'
        "
        class="text-body-1"
      >
        {{ t("platform.show-playables") }}
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
      <v-btn value="all" size="small"
        ><v-icon size="x-large">mdi-cancel</v-icon>
      </v-btn>
      <v-tooltip text="Show playable ROMs only" location="bottom">
        <template #activator="{ props }">
          <v-btn
            value="playables"
            size="small"
            v-bind="props"
            :disabled="fetchTotalRoms > 10000"
          >
            <v-icon size="x-large">mdi-play</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
      <v-tooltip text="Show non-playable ROMs only" location="bottom">
        <template #activator="{ props }">
          <v-btn
            value="not-playables"
            size="small"
            v-bind="props"
            :disabled="fetchTotalRoms > 10000"
          >
            <v-icon size="x-large">mdi-play-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
    </v-btn-toggle>
  </div>
</template>
