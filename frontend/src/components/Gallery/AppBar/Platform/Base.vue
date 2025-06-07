<script setup lang="ts">
import BaseGalleryAppBar from "@/components/Gallery/AppBar/Base.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import FirmwareBtn from "@/components/Gallery/AppBar/Platform/FirmwareBtn.vue";
import FirmwareDrawer from "@/components/Gallery/AppBar/Platform/FirmwareDrawer.vue";
import PlatformInfoDrawer from "@/components/Gallery/AppBar/Platform/PlatformInfoDrawer.vue";
import storeRoms from "@/stores/roms";
import storeNavigation from "@/stores/navigation";
import { storeToRefs } from "pinia";

// Props
const romsStore = storeRoms();
const navigationStore = storeNavigation();
const { currentPlatform } = storeToRefs(romsStore);
const { activePlatformInfoDrawer } = storeToRefs(navigationStore);
</script>

<template>
  <base-gallery-app-bar :show-playables-filter="false" show-filter-bar>
    <template #prepend>
      <v-btn
        v-if="currentPlatform"
        variant="text"
        rounded="0"
        icon="mdi-cog"
        :color="activePlatformInfoDrawer ? 'primary' : ''"
        @click="navigationStore.switchActivePlatformInfoDrawer"
      >
        <platform-icon
          :slug="currentPlatform.slug"
          :name="currentPlatform.name"
          :fs-slug="currentPlatform.fs_slug"
          :size="36"
          class="mx-3"
        />
        <v-icon
          icon="mdi-cog"
          size="xs"
          class="position-absolute"
          style="bottom: 4px; right: 4px"
        ></v-icon>
      </v-btn>
      <firmware-btn />
    </template>
  </base-gallery-app-bar>

  <firmware-drawer />
  <platform-info-drawer />
</template>

<style scoped>
.platform-icon {
  transition:
    filter 0.15s ease-in-out,
    transform 0.15s ease-in-out;
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-primary)));
}

.platform-icon:hover,
.platform-icon.active {
  filter: drop-shadow(0px 0px 3px rgba(var(--v-theme-primary)));
  transform: scale(1.1);
}
</style>
