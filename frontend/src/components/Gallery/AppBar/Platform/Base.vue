<script setup lang="ts">
import FirmwareBtn from "@/components/Gallery/AppBar/Platform/FirmwareBtn.vue";
import FirmwareDrawer from "@/components/Gallery/AppBar/Platform/FirmwareDrawer.vue";
import PlatformInfoDrawer from "@/components/Gallery/AppBar/Platform/PlatformInfoDrawer.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";

// Props
const { xs } = useDisplay();
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const navigationStore = storeNavigation();
const { activePlatformInfoDrawer } = storeToRefs(navigationStore);
</script>

<template>
  <v-app-bar
    id="gallery-app-bar"
    elevation="0"
    density="compact"
    mode="shift"
    app
    fixed
    top
  >
    <platform-icon
      v-if="currentPlatform"
      :slug="currentPlatform.slug"
      :name="currentPlatform.name"
      :size="36"
      class="mx-3 cursor-pointer platform-icon"
      :class="{ active: activePlatformInfoDrawer }"
      @click="navigationStore.switchActivePlatformInfoDrawer"
    />
    <firmware-btn />
    <filter-btn />
    <filter-text-field v-if="!xs" />
    <template #append>
      <selecting-btn />
      <gallery-view-btn />
    </template>
  </v-app-bar>

  <platform-info-drawer />
  <filter-drawer />
  <firmware-drawer />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
.platform-icon {
  transition:
    filter 0.15s ease-in-out,
    transform 0.15s ease-in-out;
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
}
.platform-icon:hover,
.platform-icon.active {
  filter: drop-shadow(0px 0px 3px rgba(var(--v-theme-romm-accent-1)));
  transform: scale(1.1);
}
</style>
