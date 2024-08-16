<script setup lang="ts">
import { useDisplay } from "vuetify";
import AdminMenu from "@/components/Gallery/AppBar/Collection/AdminMenu.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import FirmwareDrawer from "@/components/Gallery/AppBar/Platform/FirmwareDrawer.vue";
import storeAuth from "@/stores/auth";

const { xs } = useDisplay();
const auth = storeAuth();
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <filter-btn />
    <filter-text-field v-if="!xs" />
    <div v-if="xs" class="flex-grow-1" />
    <selecting-btn />
    <gallery-view-btn />
    <v-menu location="bottom">
      <template #activator="{ props }">
        <v-btn
          v-if="auth.scopes.includes('collections.write')"
          v-bind="props"
          rounded="0"
          variant="text"
          class="mr-0"
          icon="mdi-dots-vertical"
          @click.stop
        />
      </template>
      <admin-menu />
    </v-menu>
  </v-app-bar>

  <filter-drawer />
  <firmware-drawer />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
</style>
