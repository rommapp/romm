<script setup lang="ts">
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import { useDisplay } from "vuetify";

// Props
const { xs, smAndDown } = useDisplay();
</script>

<template>
  <v-app-bar
    elevation="0"
    density="compact"
    class="ma-2"
    :class="{
      'gallery-app-bar-mobile': smAndDown,
      'gallery-app-bar-desktop': !smAndDown,
    }"
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

  <filter-drawer />
</template>

<style scoped>
.gallery-app-bar-desktop {
  width: calc(100% - 108px) !important;
}
.gallery-app-bar-mobile {
  width: calc(100% - 16px) !important;
}
</style>
