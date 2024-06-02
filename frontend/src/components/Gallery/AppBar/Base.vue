<script setup lang="ts">
import AdminMenu from "@/components/Gallery/AppBar/AdminMenu.vue";
import FilterBar from "@/components/Gallery/AppBar/FilterBar.vue";
import FilterBtn from "@/components/Gallery/AppBar/FilterBtn.vue";
import FilterTextField from "@/components/Gallery/AppBar/FilterTextField.vue";
import SelectingBtn from "@/components/Gallery/AppBar/SelectingBtn.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/GalleryViewBtn.vue";
import SortBar from "@/components/Gallery/AppBar/SortBar.vue";
import storeAuth from "@/stores/auth";

// Props
const auth = storeAuth();
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <!-- <sort-btn /> -->
    <filter-btn />
    <filter-text-field />
    <selecting-btn />
    <gallery-view-btn />
    <template v-if="auth.scopes.includes('roms.write')">
      <v-menu location="bottom">
        <template #activator="{ props }">
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

  <v-expand-transition>
    <sort-bar />
  </v-expand-transition>
  <v-expand-transition>
    <filter-bar />
  </v-expand-transition>
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
