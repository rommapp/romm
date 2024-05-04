<script setup lang="ts">
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import type { Emitter } from "mitt";
import { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { xs, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const selectedPlatform = ref<Platform | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showFirmwareDialog", (platform) => {
  selectedPlatform.value = platform;
  show.value = true;
});

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function removeFileFromList(file: string) {
  filesToUpload.value = filesToUpload.value.filter((f) => f.name !== file);
}

function closeDialog() {
  show.value = false;
  filesToUpload.value = [];
  selectedPlatform.value = null;
}

function uploadFirmware() {}
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
            <v-icon icon="mdi-memory" class="ml-5" />
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

      <v-toolbar density="compact" class="bg-primary">
        <v-row class="align-center" no-gutters>
          <v-col>
            <v-btn
              block
              icon=""
              class="text-romm-accent-1 bg-terciary"
              rounded="0"
              variant="text"
              @click="triggerFileInput"
            >
              <v-icon :class="{ 'mr-2': !xs }">mdi-plus</v-icon>
              <span v-if="!xs">Add firmware</span>
            </v-btn>
            <v-file-input
              class="file-input"
              id="file-input"
              @keyup.enter="uploadFirmware()"
              v-model="filesToUpload"
              multiple
              required
            />
          </v-col>
          <v-col cols="2">
            <v-btn
              block
              icon=""
              class="text-romm-green-1 bg-terciary"
              rounded="0"
              variant="text"
              @click="uploadFirmware()"
              :disabled="filesToUpload.length == 0 || selectedPlatform == null"
            >
              Upload
            </v-btn>
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text
        v-if="filesToUpload.length > 0"
        class="scroll bg-terciary py-2 px-8"
      >
        <v-row
          v-for="file in filesToUpload"
          class="py-2 align-center"
          no-gutters
        >
          <v-col cols="8" lg="9">
            {{ file.name }}
          </v-col>
          <v-col cols="3" lg="2">
            [<span class="text-romm-accent-1">{{ formatBytes(file.size) }}</span
            >]
          </v-col>
          <v-col cols="1"
            ><v-btn
              @click="removeFileFromList(file.name)"
              icon
              size="x-small"
              rounded="0"
              variant="text"
              class="pa-0 ma-0"
              ><v-icon class="text-romm-red">mdi-delete</v-icon></v-btn
            ></v-col
          >
        </v-row>
      </v-card-text>

      <v-card-text class="my-4 py-0"> </v-card-text>
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
