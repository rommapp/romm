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
const { filterVerified } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");

// Computed property to determine current state
const currentState = computed(() => {
  if (filterVerified.value === true) return "verified";
  if (filterVerified.value === false) return "not-verified";
  return "all"; // null
});

// Handler for state changes
function setState(state: string | null) {
  if (!state) return;

  galleryFilterStore.setFilterVerifiedState(
    state as "all" | "verified" | "not-verified",
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
        mdi-check-decagram
      </v-icon>
      <span
        :class="
          currentState !== 'all'
            ? 'text-primary font-weight-medium'
            : 'text-medium-emphasis'
        "
        class="text-body-1"
      >
        {{ t("platform.show-verified") }}
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
      <v-tooltip text="Show verified ROMs only" location="bottom">
        <template #activator="{ props }">
          <v-btn value="verified" size="small" v-bind="props">
            <v-icon size="x-large">mdi-check-decagram</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
      <v-tooltip text="Show non-verified ROMs only" location="bottom">
        <template #activator="{ props }">
          <v-btn value="not-verified" size="small" v-bind="props">
            <v-icon size="x-large">mdi-check-decagram-outline</v-icon>
          </v-btn>
        </template>
      </v-tooltip>
    </v-btn-toggle>
  </div>
</template>
