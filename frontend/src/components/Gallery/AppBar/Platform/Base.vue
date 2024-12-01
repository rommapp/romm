<script setup lang="ts">
import FirmwareBtn from "@/components/Gallery/AppBar/Platform/FirmwareBtn.vue";
import FirmwareDrawer from "@/components/Gallery/AppBar/Platform/FirmwareDrawer.vue";
import FilterBtn from "@/components/Gallery/AppBar/common/FilterBtn.vue";
import FilterDrawer from "@/components/Gallery/AppBar/common/FilterDrawer/Base.vue";
import FilterTextField from "@/components/Gallery/AppBar/common/FilterTextField.vue";
import GalleryViewBtn from "@/components/Gallery/AppBar/common/GalleryViewBtn.vue";
import SelectingBtn from "@/components/Gallery/AppBar/common/SelectingBtn.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RSection from "@/components/common/RSection.vue";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import storeAuth from "@/stores/auth";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const { xs } = useDisplay();
const viewportWidth = ref(window.innerWidth);
const heartbeat = storeHeartbeat();
const romsStore = storeRoms();
const scanningStore = storeScanning();
const { scanning } = storeToRefs(scanningStore);
const { currentPlatform } = storeToRefs(romsStore);
const auth = storeAuth();
const navigationStore = storeNavigation();
const { activePlatformInfoDrawer, activePlatformSettingsDrawer } =
  storeToRefs(navigationStore);
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

const platformInfoFields = [
  { key: "name", label: "Name" },
  { key: "slug", label: "Slug" },
  { key: "fs_slug", label: "Filesystem folder name" },
  { key: "category", label: "Category" },
  { key: "generation", label: "Generation" },
  { key: "family_name", label: "Family" },
];

// Functions
async function scan() {
  scanningStore.set(true);

  if (!socket.connected) socket.connect();

  socket.emit("scan", {
    platforms: [romsStore.currentPlatform?.id],
    type: "quick",
    apis: heartbeat.getMetadataOptions().map((s) => s.value),
  });
}

function setAspectRatio() {
  // TODO: save aspect ratio on database
  console.log(aspectRatioOptions.value[selectedAspectRatio.value]);
}
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
      class="mx-3 platform-icon"
      :class="{ active: activePlatformInfoDrawer }"
      @click="navigationStore.switchActivePlatformInfoDrawer"
    />
    <firmware-btn />
    <filter-btn />
    <filter-text-field v-if="!xs" />
    <div v-if="xs" class="flex-grow-1" />
    <selecting-btn />
    <gallery-view-btn />
  </v-app-bar>

  <v-navigation-drawer
    v-model="activePlatformInfoDrawer"
    floating
    mobile
    :width="xs ? viewportWidth : '500'"
    v-if="currentPlatform"
  >
    <v-row no-gutters class="justify-center align-center">
      <v-col cols="12">
        <div class="text-center">
          <platform-icon
            :slug="currentPlatform.slug"
            :name="currentPlatform.name"
            class="platform-icon-big"
            :size="160"
          />
        </div>
        <div class="text-center">
          <v-btn
            class="bg-terciary"
            @click="emitter?.emit('showUploadRomDialog', currentPlatform)"
          >
            <v-icon class="text-romm-green mr-2">mdi-upload</v-icon>
            Upload roms
          </v-btn>
          <v-btn
            :disabled="scanning"
            rounded="4"
            :loading="scanning"
            @click="scan"
            class="ml-2 bg-terciary"
          >
            <template #prepend>
              <v-icon :color="scanning ? '' : 'romm-accent-1'"
                >mdi-magnify-scan</v-icon
              >
            </template>
            Scan platform
            <template #loader>
              <v-progress-circular
                color="romm-accent-1"
                :width="2"
                :size="20"
                indeterminate
              />
            </template>
          </v-btn>
        </div>
        <div class="mt-4 text-center">
          <a
            v-if="currentPlatform.igdb_id"
            style="text-decoration: none; color: inherit"
            :href="currentPlatform.url ? currentPlatform.url : ''"
            target="_blank"
          >
            <v-chip size="x-small" @click.stop>
              <span>IGDB</span>
              <v-divider class="mx-2 border-opacity-25" vertical />
              <span>ID: {{ currentPlatform.igdb_id }}</span>
            </v-chip>
          </a>
          <v-chip
            size="x-small"
            class="ml-1"
            @click.stop
            :class="{ 'ml-1': currentPlatform.igdb_id }"
            v-if="currentPlatform.moby_id"
          >
            <span>Mobygames</span>
            <v-divider class="mx-2 border-opacity-25" vertical />
            <span>ID: {{ currentPlatform.moby_id }}</span>
          </v-chip>
        </div>
        <v-card class="mt-4 mx-4 bg-terciary fill-width" elevation="0">
          <v-card-text class="pa-4">
            <template
              v-for="(field, index) in platformInfoFields"
              :key="field.key as string"
            >
              <div
                v-if="currentPlatform[field.key]"
                :class="{ 'mt-4': index !== 0 }"
              >
                <p class="text-subtitle-1 text-decoration-underline">
                  {{ field.label }}
                </p>
                <p class="text-subtitle-2">
                  {{ currentPlatform[field.key] }}
                </p>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <v-row class="mt-4" no-gutters>
      <v-col cols="12">
        <r-section icon="mdi-aspect-ratio" title="UI Settings" elevation="0">
          <template #content>
            <v-item-group
              v-model="selectedAspectRatio"
              mandatory
              @update:model-value="setAspectRatio"
            >
              <v-row no-gutters class="text-center justify-center align-center">
                <v-col class="ma-2" v-for="aspectRatio in aspectRatioOptions">
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
                        <p class="text-center mx-2 text-caption">
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
        <r-section
          icon="mdi-alert"
          icon-color="red"
          title="Danger zone"
          elevation="0"
        >
          <template #content>
            <div class="text-center my-2">
              <v-btn
                class="text-romm-red bg-terciary"
                variant="flat"
                @click="
                  emitter?.emit('showDeletePlatformDialog', currentPlatform)
                "
              >
                <v-icon class="text-romm-red mr-2">mdi-delete</v-icon>
                Delete platform
              </v-btn>
            </div>
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
.greyscale {
  filter: grayscale(100%);
}
</style>
