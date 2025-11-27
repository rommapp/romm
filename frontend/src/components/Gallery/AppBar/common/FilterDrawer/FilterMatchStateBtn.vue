<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { inject } from "vue";
import { useI18n } from "vue-i18n";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { filterMatched, filterUnmatched } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Computed property to determine current state
const matchState = computed(() => {
  if (filterMatched.value) return "matched";
  if (filterUnmatched.value) return "unmatched";
  return "all";
});

// Handler for state changes
function setMatchState(state: string) {
  switch (state) {
    case "matched":
      galleryFilterStore.setFilterMatched(true);
      break;
    case "unmatched":
      galleryFilterStore.setFilterUnmatched(true);
      break;
    default: // "all"
      galleryFilterStore.setFilterMatched(false);
      galleryFilterStore.setFilterUnmatched(false);
      break;
  }
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <div
    class="d-flex align-center justify-space-between py-2 px-4 rounded-lg border"
  >
    <div class="d-flex align-center">
      <v-icon
        :color="matchState !== 'all' ? 'primary' : 'grey-lighten-1'"
        class="mr-3"
      >
        mdi-file-search-outline
      </v-icon>
      <span
        :class="
          matchState !== 'all'
            ? 'text-primary font-weight-medium'
            : 'text-medium-emphasis'
        "
        class="text-body-1"
      >
        Match Status
      </span>
    </div>
    <v-btn-toggle
      :model-value="matchState"
      color="primary"
      density="compact"
      variant="outlined"
      @update:model-value="setMatchState"
    >
      <v-btn value="all" size="small"> All </v-btn>
      <v-tooltip :text="t('platform.show-matched')" location="bottom">
        <template #activator="{ props }">
          <v-btn value="matched" size="small" v-bind="props">
            <v-icon size="x-large">mdi-file-find</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
      <v-tooltip :text="t('platform.show-unmatched')" location="bottom">
        <template #activator="{ props }">
          <v-btn value="unmatched" size="small" v-bind="props">
            <v-icon size="x-large">mdi-file-find-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
    </v-btn-toggle>
  </div>
</template>
