<script setup lang="ts">
import storeAuth from "@/stores/auth";
import FilterBar from "@/components/Gallery/AppBar/FilterBar.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/GalleryViewBtn.vue";
import AdminMenu from "@/components/Gallery/AppBar/AdminMenu.vue";

// Props
const auth = storeAuth();
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <v-btn class="ml-0" variant="text" rounded="0" icon="mdi-sort" @click="" />
    <v-btn class="ml-0" variant="text" rounded="0" icon="mdi-filter-variant" @click="" />
    <filter-bar />
    <gallery-view-btn />
    <template v-if="auth.scopes.includes('roms.write')">
      <v-menu location="bottom">
        <template v-slot:activator="{ props }">
          <v-btn
            v-bind="props"
            @click=""
            rounded="0"
            variant="text"
            class="mr-0"
            icon="mdi-dots-vertical"
          />
        </template>
        <admin-menu />
      </v-menu>
    </template>
  </v-app-bar>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
