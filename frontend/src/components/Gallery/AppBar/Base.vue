<script setup lang="ts">
import AdminMenu from "@/components/Gallery/AppBar/AdminMenu.vue";
import FilterBar from "@/components/Gallery/AppBar/FilterBar.vue";
import FilterUnmatchedBtn from "@/components/Gallery/AppBar/FilterUnmatchedBtn.vue";
import FilterBtn from "@/components/Gallery/AppBar/FilterBtn.vue";
import FilterTextField from "@/components/Gallery/AppBar/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/GalleryViewBtn.vue";
import SortBar from "@/components/Gallery/AppBar/SortBar.vue";
import SortBtn from "@/components/Gallery/AppBar/SortBtn.vue";
import storeAuth from "@/stores/auth";

// Props
const auth = storeAuth();
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <sort-btn />
    <filter-btn />
    <filter-unmatched-btn />
    <filter-text-field />
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
  <sort-bar />
  <filter-bar />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
