<script setup lang="ts">
import AdminMenu from "@/components/Gallery/AppBar/Platform/AdminMenu.vue";
import FirmwareBtn from "@/components/Gallery/AppBar/Platform/FirmwareBtn.vue";
import FirmwareDrawer from "@/components/Gallery/AppBar/Platform/FirmwareDrawer.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import storeAuth from "@/stores/auth";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

const { xs } = useDisplay();
const romsStore = storeRoms();
const { currentPlatform, currentCollection } = storeToRefs(romsStore);

// Props
const auth = storeAuth();
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact">
    <platform-icon
      v-if="currentPlatform"
      :slug="currentPlatform.slug"
      :name="currentPlatform.name"
      :size="36"
      class="ml-3 mr-2 platform-icon"
    />
    <firmware-btn />
    <filter-btn />
    <filter-text-field v-if="!xs" />
    <div v-if="xs" class="flex-grow-1" />
    <selecting-btn />
    <gallery-view-btn />
    <v-menu location="bottom">
      <template #activator="{ props }">
        <v-btn
          v-if="auth.scopes.includes('roms.write')"
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
.platform-icon {
  filter: drop-shadow(0px 0px 2px #a452fe);
}
</style>
