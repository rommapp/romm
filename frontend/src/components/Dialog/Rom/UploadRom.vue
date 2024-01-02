<script setup lang="ts">
import { ref, inject, onBeforeUnmount } from "vue";
import { useRoute } from "vue-router";
import { useDisplay } from "vuetify";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import socket from "@/services/socket";
import api from "@/services/api";
import storeScanning from "@/stores/scanning";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const route = useRoute();
const show = ref(false);
const romsToUpload = ref([]);
const scanning = storeScanning();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showUploadRomDialog", () => {
  show.value = true;
});

socket.on("scan:done", () => {
  scanning.set(false);
  socket.disconnect();
  emitter?.emit("refreshDrawer");
  emitter?.emit("snackbarShow", {
    msg: "Scan completed successfully!",
    icon: "mdi-check-bold",
    color: "green",
  });
});

socket.on("scan:done_ko", (msg) => {
  scanning.set(false);
  emitter?.emit("snackbarShow", {
    msg: `Scan couldn't be completed. Something went wrong: ${msg}`,
    icon: "mdi-close-circle",
    color: "red",
  });
  socket.disconnect();
});

async function uploadRoms() {
  show.value = false;
  scanning.set(true);
  emitter?.emit("snackbarShow", {
    msg: `Uploading ${romsToUpload.value.length} roms to ${route.params.platform}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await api
    .uploadRoms({
      romsToUpload: romsToUpload.value,
      platform: route.params.platform,
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
          platforms: [route.params.platform],
          rescan: false,
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
    })
    .finally(() => {
      scanning.set(false);
    });
}

onBeforeUnmount(() => {
  socket.off("scan:done");
  socket.off("scan:done_ko");
});
</script>

<template>
  <v-dialog
    :modelValue="show"
    scroll-strategy="none"
    width="auto"
    :scrim="false"
    @click:outside="show = false"
    @keydown.esc="show = false"
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
              @click="show = false"
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

      <v-card-text>
        <v-row class="pa-2" no-gutters>
          <v-file-input
            @keyup.enter="uploadRoms()"
            :label="`Upload rom(s) to ${route.params.platform}`"
            v-model="romsToUpload"
            prepend-inner-icon="mdi-disc"
            prepend-icon=""
            multiple
            chips
            required
            variant="outlined"
            hide-details
          />
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
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
</style>
