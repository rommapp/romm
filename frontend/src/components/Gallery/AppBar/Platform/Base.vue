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
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs } = useDisplay();
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const auth = storeAuth();
const navigationStore = storeNavigation();
const { activePlatformInfoDrawer } = storeToRefs(navigationStore);
const selectedAspectRatio = ref(2);
const aspectRatioOptions = computed(() => [
  {
    name: "2 / 3",
    size: 2 / 3,
    source: "SteamGridDB",
  },
  {
    name: "3 / 4",
    size: 3 / 4,
    source: "IGDB / MobyGames",
  },
  {
    name: "1 / 1",
    size: 1 / 1,
    source: "Old squared cases",
  },
]);

function setAspectRatio() {
  // TODO: save aspect ratio on database
  console.log(aspectRatioOptions.value[selectedAspectRatio.value]);
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
    :scrim="false"
    v-if="currentPlatform"
  >
    <!-- <v-row no-gutters class="justify-center mx-auto">
      <v-col cols="auto">
        <platform-icon
          :slug="currentPlatform.slug"
          :name="currentPlatform.name"
          class="platform-icon-big"
          :size="160"
        />
      </v-col>
      <v-col cols="auto"
        ><v-img
          max-width="200"
          v-if="currentPlatform.url_logo"
          :src="currentPlatform.url_logo"
      /></v-col>
    </v-row> -->
    <v-row no-gutters class="justify-center">
      <v-col>
        <r-section icon="mdi-aspect-ratio" title="Cover aspect ratio">
          <template #content>
            <v-item-group
              v-model="selectedAspectRatio"
              mandatory
              @update:model-value="setAspectRatio"
            >
              <v-row no-gutters class="align-center">
                <v-col
                  cols="4"
                  sm="3"
                  md="2"
                  class="pa-2 mx-auto"
                  v-for="aspectRatio in aspectRatioOptions"
                >
                  <v-item v-slot="{ isSelected, toggle }">
                    <v-card
                      :color="isSelected ? 'romm-accent-1' : 'romm-gray'"
                      variant="outlined"
                      @click="toggle"
                    >
                      <v-card-text
                        class="pa-0 text-center align-center justify-center"
                      >
                        <v-img
                          :aspect-ratio="aspectRatio.size"
                          cover
                          src="/assets/login_bg.png"
                          :class="{ greyscale: !isSelected }"
                          class="d-flex align-center justify-center"
                        >
                          <p class="text-h5 text-romm-white">
                            {{ aspectRatio.name }}
                          </p>
                        </v-img>
                        <p class="text-center text-caption">
                          {{ aspectRatio.source }}
                        </p>
                      </v-card-text>
                    </v-card>
                  </v-item>
                </v-col>
              </v-row>
            </v-item-group>
          </template>
        </r-section>
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
.platform-icon-big {
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
}
#platform-info-drawer {
  z-index: 3 !important;
  height: calc(100dvh - 48px) !important;
}
.greyscale {
  filter: grayscale(100%);
}
</style>
