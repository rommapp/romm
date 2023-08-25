<script setup>
import FilterBar from "@/components/GalleryAppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/GalleryAppBar/GalleryViewBtn.vue";
import ScanBtn from "@/components/GalleryAppBar/ScanBtn.vue";
import UploadRomBtn from "@/components/GalleryAppBar/UploadRomBtn.vue";
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <filter-bar />
    <gallery-view-btn />
    <upload-rom-btn />
    <scan-btn />
  </v-app-bar>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
