<script setup lang="ts">
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import CharIndexBar from "@/components/Gallery/AppBar/common/CharIndexBar.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { computed } from "vue";

// Props
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
    <filter-btn />
    <template v-if="!xs">
      <search-text-field />
    </template>
    <template #append>
      <search-btn v-if="!xs" />
      <selecting-btn />
      <gallery-view-btn />
    </template>
  </v-app-bar>

  <char-index-bar />
  <filter-drawer />
</template>
