<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";

import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import saveApi from "@/services/api/save";
import storeRoms, { type Rom } from "@/stores/roms";

import type { SaveSchema } from "@/__generated__";

const props = defineProps<{ rom: Rom }>();
const savesToUpload = ref<File[]>([]);
const selectedSaves = ref<SaveSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();

emitter?.on("romUpdated", (rom) => {
  if (rom?.id === props.rom.id) {
    props.rom.user_saves = rom.user_saves;
  }
});

async function downloadSaves() {
  selectedSaves.value.map((save) => {
    const a = document.createElement("a");
    a.href = save.download_path;
    a.download = `${save.file_name}`;
    a.click();
  });

  selectedSaves.value = [];
}

async function uploadSaves() {
  emitter?.emit("snackbarShow", {
    msg: `Uploading ${savesToUpload.value.length} saves to ${props.rom.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await saveApi
    .uploadSaves({
      saves: savesToUpload.value,
      rom: props.rom,
    })
    .then(({ data }) => {
      const { saves, uploaded } = data;
      props.rom.user_saves = saves;
      romsStore.update(props.rom);
      savesToUpload.value = [];

      emitter?.emit("snackbarShow", {
        msg: `Uploaded ${uploaded} files successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload saves: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
}
</script>
<template>
  <v-row class="pa-2 align-center" no-gutters>
    <v-col>
      <v-list-item class="px-0">
        <v-file-input
          @keyup.enter="uploadSaves()"
          :label="`Upload ${props.rom.name}`"
          v-model="savesToUpload"
          prepend-inner-icon="mdi-file"
          prepend-icon=""
          multiple
          chips
          required
          variant="outlined"
          density="compact"
          hide-details
        />
        <template v-slot:append>
          <v-btn
            @click="uploadSaves()"
            class="text-romm-green ml-3 bg-terciary"
          >
            Upload
          </v-btn>
        </template>
      </v-list-item>
    </v-col>
  </v-row>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      class="px-3"
      v-for="save in rom.user_saves"
      :key="save.id"
      :title="save.file_name"
      :subtitle="`${save.emulator || 'unknown'} - ${formatBytes(save.file_size_bytes)}`"
    >
      <template v-slot:prepend>
        <v-checkbox
          v-model="selectedSaves"
          :value="save"
          color="romm-accent-1"
          hide-details
        />
      </template>
      <template v-slot:append>
        <v-btn
          icon
          :href="save.download_path"
          rounded="0"
          variant="text"
          class="bg-terciary"
          size="small"
          download
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
      </template>
    </v-list-item>
  </v-list>
  <v-btn
    :disabled="!selectedSaves.length"
    @click="downloadSaves()"
    rounded="0"
    variant="text"
    class="mt-3 mr-3 bg-terciary"
  >
    <v-icon>mdi-download</v-icon>
    Download
  </v-btn>
  <v-btn
    :disabled="!selectedSaves.length"
    @click="
      emitter?.emit('showDeleteSavesDialog', {
        rom: props.rom,
        saves: selectedSaves,
      })
    "
    rounded="0"
    variant="text"
    class="mt-3 bg-terciary text-romm-red"
  >
    <v-icon>mdi-delete</v-icon>
    Delete
  </v-btn>
</template>
