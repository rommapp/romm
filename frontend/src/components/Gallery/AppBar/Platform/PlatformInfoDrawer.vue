<script setup lang="ts">
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RSection from "@/components/common/RSection.vue";
import platformApi from "@/services/api/platform";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeNavigation from "@/stores/navigation";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref, watch } from "vue";
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
const { activePlatformInfoDrawer } = storeToRefs(navigationStore);
const selectedAspectRatio = ref(0);
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

watch(
  () => currentPlatform.value?.aspect_ratio,
  (aspectRatio) => {
    if (aspectRatio) {
      // Find the index of the aspect ratio option that matches the current aspect ratio
      const defaultAspectRatio = aspectRatioOptions.value.findIndex(
        (option) => Math.abs(option.size - aspectRatio) < 0.01, // Handle floating-point precision issues
      );
      // If a matching aspect ratio option is found, update the selectedAspectRatio
      if (defaultAspectRatio !== -1) {
        selectedAspectRatio.value = defaultAspectRatio;
      }
    }
  },
  { immediate: true }, // Execute the callback immediately with the current value
);

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

async function setAspectRatio() {
  if (currentPlatform.value) {
    const selectedOption = aspectRatioOptions.value[selectedAspectRatio.value];
    platformApi
      .updatePlatform({
        platform: {
          ...currentPlatform.value,
          aspect_ratio: selectedOption.size,
        },
      })
      .then(({ data }) => {
        emitter?.emit("snackbarShow", {
          msg: data.msg,
          icon: "mdi-check-bold",
          color: "green",
        });
        if (currentPlatform.value) {
          currentPlatform.value.aspect_ratio = selectedOption.size;
        }
      })
      .catch((error) => {
        emitter?.emit("snackbarShow", {
          msg: `Failed to update aspect ratio: ${
            error.response?.data?.msg || error.message
          }`,
          icon: "mdi-close-circle",
          color: "red",
        });
      });
  }
}
</script>

<template>
  <v-navigation-drawer
    v-model="activePlatformInfoDrawer"
    floating
    mobile
    :width="xs ? viewportWidth : '500'"
    v-if="currentPlatform"
  >
    <v-row no-gutters class="justify-center align-center">
      <v-col cols="12">
        <div class="text-center mt-2">
          <platform-icon
            :slug="currentPlatform.slug"
            :name="currentPlatform.name"
            class="platform-icon"
            :size="160"
          />
        </div>
        <div
          class="text-center mt-4"
          v-if="auth.scopes.includes('platforms.write')"
        >
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
              :key="field.key"
            >
              <div
                v-if="
                  currentPlatform[field.key as keyof typeof currentPlatform]
                "
                :class="{ 'mt-4': index !== 0 }"
              >
                <p class="text-subtitle-1 text-decoration-underline">
                  {{ field.label }}
                </p>
                <p class="text-subtitle-2">
                  {{
                    currentPlatform[field.key as keyof typeof currentPlatform]
                  }}
                </p>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <v-row class="mt-4" no-gutters>
      <v-col cols="12">
        <r-section
          v-if="auth.scopes.includes('platforms.write')"
          icon="mdi-aspect-ratio"
          title="UI Settings"
          elevation="0"
        >
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
          v-if="auth.scopes.includes('platforms.write')"
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
</template>
<style scoped>
.platform-icon {
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-romm-accent-1)));
}
.greyscale {
  filter: grayscale(100%);
}
</style>
