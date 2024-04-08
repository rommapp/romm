<script setup lang="ts">
import PlatformIcon from "@/components/Platform/PlatformIcon.vue";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storePlatforms, { type Platform } from "@/stores/platforms";
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
const platform = ref<Platform | null>(null);
const platforms = storePlatforms();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showUploadRomDialog", (platformWhereUpload) => {
  if (platformWhereUpload) {
    platform.value = platformWhereUpload;
  }
  show.value = true;
});

// Functions
async function uploadRoms() {
  if (!platform.value) return;
  show.value = false;
  scanningStore.set(true);
  const platformId = platform.value.id
  emitter?.emit("snackbarShow", {
    msg: `Uploading ${romsToUpload.value.length} roms to ${platform.value.name}...`,
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
  platform.value = null;
}

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function closeDialog() {
  show.value = false;
  romsToUpload.value = [];
  platform.value = null;
}
</script>

<template>
  <v-dialog
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
    no-click-animation
    persistent
  >
    <v-card
      rounded="0"
      :class="{
        'edit-content': lgAndUp,
        'edit-content-tablet': mdAndDown,
        'edit-content-mobile': xs,
      }"
    >
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="9" xs="9" sm="10" md="10" lg="11">
            <v-icon icon="mdi-upload" class="ml-5" />
          </v-col>
          <v-col>
            <v-btn
              @click="closeDialog"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text class="my-4 py-0">
        <v-select
          label="Platform"
          item-title="name"
          v-model="platform"
          :items="platforms.value"
          variant="outlined"
          rounded="0"
          density="comfortable"
          prepend-inner-icon="mdi-controller"
          prepend-icon=""
          return-object
          clearable
          hide-details
        >
          <template v-slot:item="{ props, item }">
            <v-list-item
              class="py-2"
              v-bind="props"
              :title="item.raw.name ?? ''"
            >
              <template v-slot:prepend>
                <v-avatar :rounded="0" size="35">
                  <platform-icon :key="item.raw.slug" :slug="item.raw.slug" />
                </v-avatar>
              </template>
            </v-list-item>
          </template>
        </v-select>
      </v-card-text>
      <v-card-text
        v-if="romsToUpload.length > 0"
        class="scroll bg-terciary py-2 px-8"
      >
        <v-row v-for="rom in romsToUpload" class="py-2" no-gutters>
          <v-col cols="9" lg="10">
            {{ rom.name }}
          </v-col>
          <v-col cols="3" lg="2">
            [<span class="text-romm-accent-1">{{ formatBytes(rom.size) }}</span
            >]
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-text class="mt-4 py-0">
        <v-btn
          size="large"
          block
          prepend-icon="mdi-plus"
          variant="outlined"
          class="text-romm-accent-1"
          @click="triggerFileInput"
        >
          Add games
        </v-btn>
        <v-file-input
          class="file-input"
          id="file-input"
          @keyup.enter="uploadRoms()"
          v-model="romsToUpload"
          multiple
          required
        />
      </v-card-text>
      <v-card-text class="my-4 py-0">
        <v-row class="justify-center px-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn @click="uploadRoms()" class="text-romm-green ml-5 bg-terciary">
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
