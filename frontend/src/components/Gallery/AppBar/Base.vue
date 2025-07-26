<script setup lang="ts">
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import SmartCollectionBtn from "@/components/Gallery/AppBar/common/SmartCollectionBtn.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import CharIndexBar from "@/components/Gallery/AppBar/common/CharIndexBar.vue";
import ContextualRandomBtn from "@/components/Gallery/AppBar/common/ContextualRandomBtn.vue";
import { calculateMainLayoutWidth } from "@/utils";

// Props
withDefaults(
  defineProps<{
    showPlayablesFilter?: boolean;
    showPlatformsFilter?: boolean;
    showSearchBar?: boolean;
  }>(),
  {
    showPlayablesFilter: true,
    showPlatformsFilter: false,
    showSearchBar: false,
  },
);
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
      <smart-collection-btn />
    </template>
    <search-text-field v-if="showSearchBar" />
    <slot name="content" />
    <template #append>
      <selecting-btn />
      <gallery-view-btn />
      <contextual-random-btn />
      <slot name="append" />
    </template>
  </v-app-bar>

  <filter-drawer
    :show-playables-filter="showPlayablesFilter"
    :show-platforms-filter="showPlatformsFilter"
    :show-search-bar="showSearchBar"
  />
  <char-index-bar />
</template>
