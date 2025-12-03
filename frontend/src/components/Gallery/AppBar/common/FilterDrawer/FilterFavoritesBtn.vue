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
const { filterFavorites } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Computed property to determine current state
const currentState = computed(() => {
  if (filterFavorites.value === true) return "favorites";
  if (filterFavorites.value === false) return "not-favorites";
  return "all"; // null
});

// Handler for state changes
function setState(state: string | null) {
  if (!state) return;

  galleryFilterStore.setFilterFavoritesState(
    state as "all" | "favorites" | "not-favorites",
  );
  emitter?.emit("filterRoms", null);
}
</script>

<template>
  <div class="d-flex align-center justify-space-between py-2">
    <div class="d-flex align-center">
      <v-icon
        :color="currentState !== 'all' ? 'primary' : 'grey-lighten-1'"
        class="mr-3"
      >
        mdi-star
      </v-icon>
      <span
        :class="
          currentState !== 'all'
            ? 'text-primary font-weight-medium'
            : 'text-medium-emphasis'
        "
        class="text-body-1"
      >
        {{ t("platform.show-favorites") }}
      </span>
    </div>
    <v-btn-toggle
      :model-value="currentState"
      color="primary"
      density="compact"
      variant="outlined"
      @update:model-value="setState"
    >
      <v-btn value="all" size="small"
        ><v-icon size="x-large">mdi-cancel</v-icon>
      </v-btn>
      <v-tooltip
        text="Show favorite ROMs only"
        location="bottom"
        open-delay="500"
      >
        <template #activator="{ props }">
          <v-btn value="favorites" size="small" v-bind="props">
            <v-icon size="x-large">mdi-star</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
      <v-tooltip
        text="Show non-favorite ROMs only"
        location="bottom"
        open-delay="500"
      >
        <template #activator="{ props }">
          <v-btn value="not-favorites" size="small" v-bind="props">
            <v-icon size="x-large">mdi-star-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
    </v-btn-toggle>
  </div>
</template>
