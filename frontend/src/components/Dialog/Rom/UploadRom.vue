<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const romsToUpload = ref<File[]>([]);
const scanningStore = storeScanning();
const selectedPlatform = ref<Platform | null>(null);
const supportedPlatforms = ref<Platform[]>();
const heartbeat = storeHeartbeat();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showUploadRomDialog", (platformWhereUpload) => {
  if (platformWhereUpload) {
    selectedPlatform.value = platformWhereUpload;
  }
  show.value = true;
  platformApi
    .getSupportedPlatforms()
    .then(({ data }) => {
      supportedPlatforms.value = data.sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload roms: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
});

// Functions
async function uploadRoms() {
  if (!selectedPlatform.value) return;
  show.value = false;
  scanningStore.set(true);

  if (selectedPlatform.value.id == -1) {
    await platformApi
      .uploadPlatform({ fsSlug: selectedPlatform.value.fs_slug })
      .then(({ data }) => {
        emitter?.emit("snackbarShow", {
          msg: `Platform ${selectedPlatform.value?.name} created successfully!`,
          icon: "mdi-check-bold",
          color: "green",
          timeout: 2000,
        });
        selectedPlatform.value = data;
      })
      .catch((error) => {
        console.log(error);
        emitter?.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
        return;
      })
      .finally(() => {
        emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      });
  }

  const platformId = selectedPlatform.value.id;
  emitter?.emit("snackbarShow", {
    msg: `Uploading ${romsToUpload.value.length} roms to ${selectedPlatform.value.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await romApi
    .uploadRoms({
      romsToUpload: romsToUpload.value,
      platformId: platformId,
    })
    .then(({ data }) => {
      const { uploaded_roms, skipped_roms } = data;

      if (uploaded_roms.length == 0) {
        return emitter?.emit("snackbarShow", {
          msg: `All files skipped, nothing to upload.`,
          icon: "mdi-close-circle",
          color: "orange",
          timeout: 2000,
        });
      }

      emitter?.emit("snackbarShow", {
        msg: `${uploaded_roms.length} files uploaded successfully (and ${skipped_roms.length} skipped). Starting scan...`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });

      if (!socket.connected) socket.connect();
      setTimeout(() => {
        socket.emit("scan", {
          platforms: [platformId],
          type: "quick",
          apis: heartbeat.getMetadataOptions().map((s) => s.value),
        });
      }, 2000);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload roms: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  romsToUpload.value = [];
  selectedPlatform.value = null;
}

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function removeRomFromList(romName: string) {
  romsToUpload.value = romsToUpload.value.filter((rom) => rom.name !== romName);
}

function closeDialog() {
  show.value = false;
  romsToUpload.value = [];
  selectedPlatform.value = null;
}
</script>

<template>
  <v-dialog
    :model-value="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    no-click-animation
    persistent
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card
      rounded="0"
      :class="{
        'edit-content': lgAndUp,
        'edit-content-tablet': mdAndDown,
        'edit-content-mobile': xs,
      }"
    >
      <v-toolbar
        density="compact"
        class="bg-terciary"
      >
        <v-row
          class="align-center"
          no-gutters
        >
          <v-col
            cols="9"
            xs="9"
            sm="10"
            md="10"
            lg="11"
          >
            <v-icon
              icon="mdi-upload"
              class="ml-5"
            />
          </v-col>
          <v-col>
            <v-btn
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
              @click="closeDialog"
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider
        class="border-opacity-25"
        :thickness="1"
      />

      <v-toolbar
        density="compact"
        class="bg-primary"
      >
        <v-row
          class="align-center"
          no-gutters
        >
          <v-col
            cols="10"
            sm="8"
            lg="9"
          >
            <v-autocomplete
              v-model="selectedPlatform"
              label="Platform"
              item-title="name"
              :items="supportedPlatforms"
              prepend-inner-icon="mdi-controller"
              prepend-icon=""
              return-object
              clearable
              hide-details
            >
              <template #item="{ props, item }">
                <v-list-item
                  class="py-2"
                  v-bind="props"
                  :title="item.raw.name ?? ''"
                >
                  <template #prepend>
                    <v-avatar
                      :rounded="0"
                      size="35"
                    >
                      <platform-icon
                        :key="item.raw.slug"
                        :slug="item.raw.slug"
                      />
                    </v-avatar>
                  </template>
                </v-list-item>
              </template>
            </v-autocomplete>
          </v-col>
          <v-col>
            <v-btn
              block
              icon=""
              class="text-romm-accent-1 bg-terciary"
              rounded="0"
              variant="text"
              @click="triggerFileInput"
            >
              <v-icon :class="{ 'mr-2': !xs }">
                mdi-plus
              </v-icon><span v-if="!xs">Add roms</span>
            </v-btn>
            <v-file-input
              id="file-input"
              v-model="romsToUpload"
              class="file-input"
              multiple
              required
              @keyup.enter="uploadRoms()"
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider
        class="border-opacity-25"
        :thickness="1"
      />

      <v-card-text
        v-if="romsToUpload.length > 0"
        class="scroll bg-terciary py-2 px-8"
      >
        <v-row
          v-for="rom in romsToUpload"
          :key="rom.name"
          class="py-2 align-center"
          no-gutters
        >
          <v-col
            cols="8"
            lg="9"
          >
            {{ rom.name }}
          </v-col>
          <v-col
            cols="3"
            lg="2"
          >
            [<span class="text-romm-accent-1">{{ formatBytes(rom.size) }}</span>]
          </v-col>
          <v-col cols="1">
            <v-btn
              icon
              size="x-small"
              rounded="0"
              variant="text"
              class="pa-0 ma-0"
              @click="removeRomFromList(rom.name)"
            >
              <v-icon class="text-romm-red">
                mdi-delete
              </v-icon>
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>

      <v-card-text class="my-4 py-0">
        <v-row
          class="justify-center px-2"
          no-gutters
        >
          <v-btn
            class="bg-terciary"
            @click="closeDialog"
          >
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-green ml-5 bg-terciary"
            :disabled="romsToUpload.length == 0 || selectedPlatform == null"
            @click="uploadRoms()"
          >
            Upload
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.edit-content {
  width: 900px;
}

.edit-content-tablet {
  width: 570px;
}

.edit-content-mobile {
  width: 85vw;
}

.file-input {
  display: none;
}

.scroll {
  overflow-y: scroll;
}
</style>
