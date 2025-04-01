<script setup lang="ts">
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import CharIndexBar from "@/components/Gallery/AppBar/common/CharIndexBar.vue";
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { computed } from "vue";

// Props
withDefaults(
  defineProps<{
    showPlatformsFilter?: boolean;
    showFilterBar?: boolean;
    showSearchBar?: boolean;
  }>(),
  {
    showPlatformsFilter: false,
    showFilterBar: false,
    showSearchBar: false,
  },
);
const { xs, smAndDown } = useDisplay();
const navigationStore = storeNavigation();
const { mainBarCollapsed } = storeToRefs(navigationStore);
// Computed property for dynamic width
const computedWidth = computed(() => {
  return smAndDown.value
    ? "calc(100% - 16px) !important"
    : mainBarCollapsed.value
      ? "calc(100% - 76px) !important"
      : "calc(100% - 116px) !important";
});
</script>
<template>
  <v-app-bar
    elevation="0"
    density="compact"
    class="ma-2"
    :style="{ width: computedWidth }"
    rounded
  >
    <template #prepend>
      <slot name="prepend" />
      <filter-btn />
    </template>
    <filter-text-field v-if="!xs && showFilterBar" />
    <search-text-field v-if="!xs && showSearchBar" />
    <slot name="content" />
    <template #append>
      <search-btn v-if="!xs && showSearchBar" />
      <slot name="append" />
      <selecting-btn />
      <gallery-view-btn />
    </template>
  </v-app-bar>

  <filter-drawer
    :show-platforms-filter="showPlatformsFilter"
    :show-filter-bar="showFilterBar"
    :show-search-bar="showSearchBar"
  />
  <char-index-bar />
</template>
