<script setup>
import storeAuth from "@/stores/auth";
import FilterBar from "@/components/GalleryAppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/GalleryAppBar/GalleryViewBtn.vue";
import ScanBtn from "@/components/GalleryAppBar/ScanBtn.vue";
import UploadRomBtn from "@/components/GalleryAppBar/UploadRomBtn.vue";

// Props
const auth = storeAuth();
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <filter-bar />
    <gallery-view-btn />
    <template v-if="auth.scopes.includes('roms.write')">
      <upload-rom-btn />
      <scan-btn />
    </template>
  </v-app-bar>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
