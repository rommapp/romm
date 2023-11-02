<script setup>
import storeAuth from "@/stores/auth";
import FilterBar from "@/components/Gallery/AppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/GalleryViewBtn.vue";
import ScanBtn from "@/components/Gallery/AppBar/ScanBtn.vue";
import UploadRomBtn from "@/components/Gallery/AppBar/UploadRomBtn.vue";

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
