<script setup lang="ts">
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SearchTextField from "@/components/Gallery/AppBar/Search/SearchTextField.vue";
import PlatformSelector from "@/components/Gallery/AppBar/Search/PlatformSelector.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import SearchBtn from "@/components/Gallery/AppBar/Search/SearchBtn.vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const { xs } = useDisplay();
</script>

<template>
  <v-app-bar
    top
    id="gallery-app-bar"
    elevation="0"
    density="compact"
    mode="shift"
    class="rounded mx-2 mt-2 mb-1 position-sticky"
    style="width: unset; top: 0.5rem"
  >
    <filter-btn />
    <template v-if="!xs">
      <search-text-field />
      <platform-selector />
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
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
