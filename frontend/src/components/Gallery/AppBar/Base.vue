<script setup lang="ts">
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import CharIndexBar from "@/components/Gallery/AppBar/common/CharIndexBar.vue";
import { useDisplay } from "vuetify";
import { calculateMainLayoutWidth } from "@/utils";

// Props
withDefaults(
  defineProps<{
    showPlayablesFilter?: boolean;
    showPlatformsFilter?: boolean;
    showFilterBar?: boolean;
    showSearchBar?: boolean;
  }>(),
  {
    showPlayablesFilter: true,
    showPlatformsFilter: false,
    showFilterBar: false,
    showSearchBar: false,
  },
);
const { xs } = useDisplay();
const { calculatedWidth } = calculateMainLayoutWidth();
</script>
<template>
  <v-app-bar
    elevation="0"
    density="compact"
    class="ma-2"
    :style="{ width: calculatedWidth }"
    rounded
  >
    <template #prepend>
      <slot name="prepend" />
      <filter-btn />
    </template>
    <filter-text-field v-if="!xs && showFilterBar" />
    <search-text-field v-if="showSearchBar" />
    <slot name="content" />
    <template #append>
      <selecting-btn />
      <gallery-view-btn />
      <slot name="append" />
    </template>
  </v-app-bar>

  <filter-drawer
    :show-playables-filter="showPlayablesFilter"
    :show-platforms-filter="showPlatformsFilter"
    :show-filter-bar="showFilterBar"
  />
  <char-index-bar />
</template>
