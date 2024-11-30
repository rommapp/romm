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
    />
    <firmware-btn />
    <filter-btn />
    <filter-text-field v-if="!xs" />
    <div v-if="xs" class="flex-grow-1" />
    <selecting-btn />
    <gallery-view-btn />
    <!-- <v-menu location="bottom"> -->
    <!-- <template #activator="{ props }"> -->
    <v-btn
      v-if="auth.scopes.includes('platforms.write')"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-information"
      :color="navigationStore.activePlatformInfoDrawer ? 'romm-accent-1' : ''"
      @click="navigationStore.switchActivePlatformInfoDrawer"
    />
    <v-btn
      v-if="auth.scopes.includes('platforms.write')"
      rounded="0"
      variant="text"
      class="mr-0"
      icon="mdi-cog"
      :color="navigationStore.activePlatformInfoDrawer ? 'romm-accent-1' : ''"
      @click="navigationStore.switchActivePlatformInfoDrawer"
    />
    <!-- </template> -->
    <!-- <admin-menu /> -->
    <!-- </v-menu> -->
  </v-app-bar>

  <v-navigation-drawer
    id="platform-info-drawer"
    location="right"
    floating
    width="345"
    mobile
    v-model="activePlatformInfoDrawer"
    :scrim="false"
    v-if="currentPlatform"
  >
    <v-row no-gutters>
      <v-col cols="12" md="auto">
        <div class="text-center">
          <platform-icon
            :slug="currentPlatform.slug"
            :name="currentPlatform.name"
            class="platform-icon-big"
            :size="160"
          />
        </div>
        <p class="text-center text-h6">{{ currentPlatform.name }}</p>
        <v-card min-width="300" class="mx-6 my-8 bg-terciary" elevation="3">
          <v-card-text class="pa-4">
            <p>Name: {{ currentPlatform.name }}</p>
            <br />
            <p>Slug: {{ currentPlatform.slug }}</p>
            <br />
            <p>Filesystem folder name: {{ currentPlatform.fs_slug }}</p>
            <br />
            <p>IGDB id: {{ currentPlatform.igdb_id }}</p>
            <br />
            <p>SGDB id: {{ currentPlatform.sgdb_id }}</p>
            <br />
            <p>MOBY id: {{ currentPlatform.moby_id }}</p>
            <br />
            <p>Category: {{ currentPlatform.category }}</p>
            <br />
            <p>Generation: {{ currentPlatform.generation }}</p>
            <br />
            <p>Family name: {{ currentPlatform.family_name }}</p>
            <br />
            <p>IGDB url: {{ currentPlatform.url }}</p>
            <br />
            <p>Created at: {{ currentPlatform.created_at }}</p>
            <br />
            <p>Updated at: {{ currentPlatform.updated_at }}</p>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col>
        <r-section
          icon="mdi-aspect-ratio"
          title="Cover aspect ratio"
          elevation="0"
        >
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
        <r-section icon="mdi-upload" title="Upload roms" elevation="0">
          <template #content> </template>
        </r-section>
        <r-section icon="mdi-delete" title="Delete platform" elevation="0">
          <template #content> </template>
        </r-section>
      </v-col>
    </v-row>
    <v-row no-gutters class="justify-center">
      <v-col> </v-col>
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
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
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
