<script setup lang="ts">
import DeletePlatformDialog from "@/components/common/Platform/Dialog/DeletePlatform.vue";
import PlatformIcon from "@/components/common/Platform/Icon.vue";
import RSection from "@/components/common/RSection.vue";
import platformApi from "@/services/api/platform";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeNavigation from "@/stores/navigation";
import type { Platform } from "@/stores/platforms";
import storePlatforms from "@/stores/platforms";
import storeRoms from "@/stores/roms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import { identity } from "lodash";

// Props
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const { smAndDown } = useDisplay();
const heartbeat = storeHeartbeat();
const romsStore = storeRoms();
const platformsStore = storePlatforms();
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
    source: t("platform.old-squared-cases"),
  },
  {
    name: "16 / 11",
    size: 16 / 11,
    source: t("platform.old-horizontal-cases"),
  },
]);
const tabIndex = computed(() => (activePlatformInfoDrawer.value ? 0 : -1));

const PLATFORM_INFO_FIELDS: {
  key: keyof Platform;
  label: string;
  format: (value: any) => string;
}[] = [
  { key: "name", label: t("common.name"), format: identity },
  { key: "slug", label: t("common.slug"), format: identity },
  { key: "fs_slug", label: t("settings.folder-name"), format: identity },
  { key: "category", label: t("platform.category"), format: identity },
  { key: "generation", label: t("platform.generation"), format: identity },
  { key: "family_name", label: t("platform.family"), format: identity },
  {
    key: "fs_size_bytes",
    label: t("common.size-on-disk"),
    format: (fs: number) => formatBytes(fs, 2),
  },
];

const updating = ref(false);
const updatedPlatform = ref({ ...currentPlatform.value });
const isEditable = ref(false);

// Functions
function showEditable() {
  updatedPlatform.value = { ...currentPlatform.value };
  isEditable.value = true;
}

function closeEditable() {
  updatedPlatform.value = { ...currentPlatform.value };
  isEditable.value = false;
}

async function updatePlatform() {
  if (!updatedPlatform.value) return;
  updating.value = true;
  isEditable.value = false;
  updatedPlatform.value.custom_name = updatedPlatform.value.display_name;
  await platformApi
    .updatePlatform({
      platform: updatedPlatform.value as Platform,
    })
    .then(({ data: platform }) => {
      emitter?.emit("snackbarShow", {
        msg: "Platform updated successfully",
        icon: "mdi-check-bold",
        color: "green",
      });
      currentPlatform.value = platform;
      platformsStore.update(platform);
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Failed to update platform: ${
          error.response?.data?.msg || error.message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
  updatedPlatform.value = { ...currentPlatform.value };
  updating.value = false;
}

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
          aspect_ratio: selectedOption.name,
        },
      })
      .then(({ data }) => {
        emitter?.emit("snackbarShow", {
          msg: "Platform updated successfully",
          icon: "mdi-check-bold",
          color: "green",
        });
        if (currentPlatform.value) {
          currentPlatform.value.aspect_ratio = selectedOption.name;
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

watch(
  () => currentPlatform.value?.aspect_ratio,
  (aspectRatio) => {
    if (aspectRatio) {
      // Find the index of the aspect ratio option that matches the current aspect ratio
      const defaultAspectRatio = aspectRatioOptions.value.findIndex(
        (option) => option.name == aspectRatio,
      );
      // If a matching aspect ratio option is found, update the selectedAspectRatio
      if (defaultAspectRatio !== -1) {
        selectedAspectRatio.value = defaultAspectRatio;
      }
    }
  },
  { immediate: true }, // Execute the callback immediately with the current value
);
</script>

<template>
  <v-navigation-drawer
    v-if="currentPlatform"
    mobile
    floating
    width="500"
    location="right"
    v-model="activePlatformInfoDrawer"
    :class="{
      'mr-2': activePlatformInfoDrawer,
      'drawer-mobile': smAndDown && activePlatformInfoDrawer,
    }"
    class="bg-surface rounded mt-4 mb-2 pa-1 unset-height"
  >
    <v-row no-gutters class="justify-center align-center pa-2">
      <v-col cols="12">
        <div class="text-center justify-center align-center">
          <div class="position-absolute append-top-right">
            <template v-if="auth.scopes.includes('platforms.write')">
              <v-btn
                v-if="!isEditable"
                :loading="updating"
                class="bg-toplayer"
                @click="showEditable"
                size="small"
                :tabindex="tabIndex"
              >
                <template #loader>
                  <v-progress-circular
                    color="primary"
                    :width="2"
                    :size="20"
                    indeterminate
                  />
                </template>
                <v-icon>mdi-pencil</v-icon></v-btn
              >
              <template v-else>
                <v-btn
                  @click="closeEditable"
                  size="small"
                  class="bg-toplayer"
                  :tabindex="tabIndex"
                  ><v-icon color="romm-red">mdi-close</v-icon></v-btn
                >
                <v-btn
                  @click="updatePlatform()"
                  size="small"
                  class="bg-toplayer ml-1"
                  :tabindex="tabIndex"
                  ><v-icon color="romm-green">mdi-check</v-icon></v-btn
                >
              </template>
            </template>
          </div>
          <platform-icon
            tabindex="-1"
            :slug="currentPlatform.slug"
            :name="currentPlatform.name"
            :fs-slug="currentPlatform.fs_slug"
            class="platform-icon"
            :size="160"
          />
        </div>
        <div
          class="text-center mt-2"
          v-if="auth.scopes.includes('platforms.write')"
        >
          <div v-if="!isEditable" class="text-h5 font-weight-bold pl-0">
            <span>{{ currentPlatform.display_name }}</span>
          </div>
          <div v-else>
            <v-text-field
              variant="outlined"
              class="text-white"
              hide-details
              density="compact"
              v-model="updatedPlatform.display_name"
              :readonly="!isEditable"
              @keyup.enter="updatePlatform()"
              :tabindex="tabIndex"
            />
          </div>
          <div class="mt-6">
            <v-btn
              class="bg-toplayer my-1"
              :tabindex="tabIndex"
              @click="emitter?.emit('showUploadRomDialog', currentPlatform)"
            >
              <v-icon class="text-romm-green mr-2"
                >mdi-cloud-upload-outline</v-icon
              >
              {{ t("platform.upload-roms") }}
            </v-btn>
            <v-btn
              :disabled="scanning"
              rounded="4"
              :loading="scanning"
              @click="scan"
              :tabindex="tabIndex"
              class="ml-2 my-1 bg-toplayer"
            >
              <template #prepend>
                <v-icon :color="scanning ? '' : 'primary'"
                  >mdi-magnify-scan</v-icon
                >
              </template>
              {{ t("scan.scan") }}
              <template #loader>
                <v-progress-circular
                  color="primary"
                  :width="2"
                  :size="20"
                  indeterminate
                />
              </template>
            </v-btn>
          </div>
        </div>
        <v-row
          v-if="
            currentPlatform.igdb_id ||
            currentPlatform.moby_id ||
            currentPlatform.ss_id
          "
          class="text-white text-shadow mt-2 text-center"
          no-gutters
        >
          <v-col cols="12">
            <a
              v-if="currentPlatform.igdb_id"
              style="text-decoration: none; color: inherit"
              :href="`https://www.igdb.com/platforms/${currentPlatform.slug}`"
              target="_blank"
              :tabindex="tabIndex"
            >
              <v-chip tabindex="-1" class="pl-0 mt-1" size="small" @click.stop>
                <v-avatar class="mr-2" size="30" rounded="0">
                  <v-img src="/assets/scrappers/igdb.png" />
                </v-avatar>
                <span>{{ currentPlatform.igdb_id }}</span>
              </v-chip>
            </a>
            <a
              v-if="currentPlatform.ss_id"
              style="text-decoration: none; color: inherit"
              :href="`https://www.screenscraper.fr/systemeinfos.php?plateforme=${currentPlatform.ss_id}`"
              target="_blank"
              :class="{
                'ml-1': currentPlatform.igdb_id || currentPlatform.moby_id,
              }"
              :tabindex="tabIndex"
            >
              <v-chip tabindex="-1" class="pl-0 mt-1" size="small" @click.stop>
                <v-avatar class="mr-2" size="30" rounded="0">
                  <v-img src="/assets/scrappers/ss.png" />
                </v-avatar>
                <span>{{ currentPlatform.ss_id }}</span>
              </v-chip>
            </a>
            <a
              v-if="currentPlatform.moby_id"
              style="text-decoration: none; color: inherit"
              target="_blank"
              :class="{ 'ml-1': currentPlatform.igdb_id }"
              :tabindex="tabIndex"
            >
              <v-chip tabindex="-1" class="pl-0 mt-1" size="small" @click.stop>
                <v-avatar class="mr-2" size="30" rounded="0">
                  <v-img src="/assets/scrappers/moby.png" />
                </v-avatar>
                <span>{{ currentPlatform.moby_id }}</span>
              </v-chip>
            </a>
            <a
              v-if="currentPlatform.ra_id"
              style="text-decoration: none; color: inherit"
              target="_blank"
              :class="{
                'ml-1':
                  currentPlatform.ra_id ||
                  currentPlatform.ss_id ||
                  currentPlatform.moby_id,
              }"
              :tabindex="tabIndex"
            >
              <v-chip tabindex="-1" class="pl-0 mt-1" size="small" @click.stop>
                <v-avatar class="mr-2" size="25" rounded="1">
                  <v-img src="/assets/scrappers/ra.png" />
                </v-avatar>
                <span>{{ currentPlatform.ra_id }}</span>
              </v-chip>
            </a>
          </v-col>
        </v-row>
        <v-card class="mt-4 bg-toplayer fill-width" elevation="0">
          <v-card-text class="pa-4 d-flex flex-wrap ga-2">
            <template v-for="field in PLATFORM_INFO_FIELDS" :key="field.key">
              <div>
                <v-chip tabindex="-1" size="small" class="px-0" label>
                  <v-chip :tabindex="tabIndex" label>{{ field.label }}</v-chip>
                  <span class="px-2">{{
                    field.format(currentPlatform[field.key]) || "N/A"
                  }}</span>
                </v-chip>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    <r-section
      v-if="auth.scopes.includes('platforms.write')"
      icon="mdi-cog"
      :title="t('platform.settings')"
      elevation="0"
      titleDivider
      bgColor="bg-toplayer"
      class="mx-2"
    >
      <template #content>
        <v-chip
          label
          variant="text"
          class="ml-2 mt-2"
          prepend-icon="mdi-aspect-ratio"
          :tabindex="tabIndex"
          >{{ t("platform.cover-style") }}</v-chip
        >
        <v-divider class="border-opacity-25 mx-2" />
        <v-item-group
          :tabindex="tabIndex"
          v-model="selectedAspectRatio"
          mandatory
          @update:model-value="setAspectRatio"
        >
          <v-row
            no-gutters
            class="text-center justify-center align-center pa-2"
          >
            <v-col
              cols="6"
              class="pa-2"
              v-for="aspectRatio in aspectRatioOptions"
            >
              <v-item v-slot="{ isSelected, toggle }">
                <v-card
                  :color="isSelected ? 'primary' : 'romm-gray'"
                  variant="outlined"
                  @click="toggle"
                >
                  <v-card-text
                    class="pa-0 text-center align-center justify-center"
                  >
                    <v-img
                      :aspect-ratio="aspectRatio.size"
                      cover
                      src="/assets/default/cover/empty.svg"
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
    <r-section
      v-if="auth.scopes.includes('platforms.write')"
      icon="mdi-alert"
      icon-color="red"
      :title="t('platform.danger-zone')"
      elevation="0"
      titleDivider
      bgColor="bg-toplayer"
      class="mt-2 mx-2"
    >
      <template #content>
        <div class="text-center">
          <v-btn
            :tabindex="tabIndex"
            class="text-romm-red bg-toplayer ma-2"
            variant="flat"
            @click="emitter?.emit('showDeletePlatformDialog', currentPlatform)"
          >
            <v-icon class="text-romm-red mr-2">mdi-delete</v-icon>
            {{ t("platform.delete-platform") }}
          </v-btn>
        </div>
      </template>
    </r-section>
  </v-navigation-drawer>

  <delete-platform-dialog />
</template>
<style scoped>
.append-top-right {
  top: 0.3rem;
  right: 0.3rem;
  z-index: 1;
}
.platform-icon {
  filter: drop-shadow(0px 0px 1px rgba(var(--v-theme-primary)));
}
</style>
