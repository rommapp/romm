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

// Props
const { xs, smAndDown, mdAndUp } = useDisplay();
const romsStore = storeRoms();
const { currentPlatform, currentCollection } = storeToRefs(romsStore);
const auth = storeAuth();
import storeNavigation from "@/stores/navigation";
const navigationStore = storeNavigation();
const { activePlatformInfoDrawer } = storeToRefs(navigationStore);

function setAspectRatio(ratio: string) {
  console.log(`Aspect ratio set to: ${ratio}`);
}
</script>

<template>
  <v-app-bar id="gallery-app-bar" elevation="0" density="compact" class="pl-3">
    <platform-icon
      v-if="currentPlatform"
      :slug="currentPlatform.slug"
      :name="currentPlatform.name"
      :size="36"
      class="mr-3 platform-icon"
      :class="{ active: activePlatformInfoDrawer }"
      @click="navigationStore.switchActivePlatformInfoDrawer"
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

  <v-navigation-drawer
    id="platform-info-drawer"
    location="top"
    floating
    mobile
    v-model="activePlatformInfoDrawer"
    class="bg-terciary"
    :scrim="false"
  >
    <v-row no-gutters>
      <v-col class="pl-4 text-center" cols="12" sm="auto">
        <platform-icon
          v-if="currentPlatform"
          :slug="currentPlatform.slug"
          :name="currentPlatform.name"
          class="platform-logo"
          :size="180"
        />
      </v-col>
      <v-col cols="auto" :class="{ 'w-30': mdAndUp }">
        <div class="pa-6">
          <p>
            The Game Boy Advance (GBA) is a 32-bit handheld game console
            developed, manufactured, and marketed by Nintendo as the successor
            to the Game Boy Color. It was released in Japan on March 21, 2001,
            in North America on June 11, 2001, in Australia and Europe on June
            22, 2001, and in mainland China as iQue Game Boy Advance on June 8,
            2004. The GBA is part of the sixth generation of video game
            consoles.
          </p>
          <br />
          <p>
            The GBA features a 2.9-inch reflective TFT color LCD screen, capable
            of displaying 32,768 colors. It is powered by a 16.8 MHz 32-bit
            ARM7TDMI CPU with embedded memory. The console is backward
            compatible with Game Boy and Game Boy Color games, making it a
            versatile device for gamers.
          </p>
          <br />
          <p>
            The GBA has a rich library of games, including popular titles such
            as Pokémon Ruby and Sapphire, The Legend of Zelda: The Minish Cap,
            and Metroid Fusion. Its compact design and extensive game library
            have made it a beloved console among gamers.
          </p>
        </div>
      </v-col>
    </v-row>
  </v-navigation-drawer>
  <filter-drawer />
  <firmware-drawer />
</template>

<style scoped>
#gallery-app-bar {
  z-index: 999 !important;
}
.platform-icon {
  cursor: pointer;
  transition: filter 0.15s ease-in-out;
}
.platform-icon {
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
}
.platform-icon:hover,
.platform-icon.active {
  filter: drop-shadow(0px 0px 3px rgba(var(--v-theme-romm-accent-1)));
}
.platform-logo {
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
}
#platform-info-drawer {
  z-index: 3 !important;
  height: calc(100dvh - 48px) !important;
}
</style>
