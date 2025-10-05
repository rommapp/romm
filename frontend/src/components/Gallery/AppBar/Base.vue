<script setup lang="ts">
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import CharIndexBar from "@/components/Gallery/AppBar/common/CharIndexBar.vue";
import ContextualRandomBtn from "@/components/Gallery/AppBar/common/ContextualRandomBtn.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import SmartCollectionBtn from "@/components/Gallery/AppBar/common/SmartCollectionBtn.vue";
import { calculateMainLayoutWidth } from "@/utils";

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
      <FilterBtn />
      <SmartCollectionBtn />
    </template>
    <SearchTextField v-if="showSearchBar" />
    <slot name="content" />
    <template #append>
      <SelectingBtn />
      <GalleryViewBtn />
      <ContextualRandomBtn />
      <slot name="append" />
    </template>
  </v-app-bar>

  <FilterDrawer
    :show-playables-filter="showPlayablesFilter"
    :show-platforms-filter="showPlatformsFilter"
    :show-search-bar="showSearchBar"
  />
  <CharIndexBar />
</template>
