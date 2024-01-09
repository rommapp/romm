<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";

import { formatBytes } from "@/utils";
import api from "@/services/api";
import storeRoms from "@/stores/roms";

import type { SaveSchema } from "@/__generated__";

const props = defineProps(["rom"]);
const savesToUpload = ref([]);
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();

async function deleteSave(save: SaveSchema) {
  await api
    .deleteSaves({
      saves: [save],
    })
    .then(({ data }) => {
      props.rom.saves = data;
      romsStore.update(props.rom);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to delete save: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
}

async function uploadSaves() {
  emitter?.emit("snackbarShow", {
    msg: `Uploading ${savesToUpload.value.length} saves to ${props.rom.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await api
    .uploadSaves({
      saves: savesToUpload.value,
      rom: props.rom,
    })
    .then(({ data }) => {
      const { saves, uploaded } = data;
      props.rom.saves = saves;
      romsStore.update(props.rom);
      savesToUpload.value = [];

      emitter?.emit("snackbarShow", {
        msg: `${uploaded} files uploaded successfully!`,
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
  <v-row class="pa-2 center" no-gutters align="center">
    <v-file-input
      @keyup.enter="uploadSaves()"
      :label="`Upload save files for ${props.rom.name}`"
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
    <v-btn @click="uploadSaves()" class="text-romm-green ml-5 bg-terciary">
      Upload
    </v-btn>
  </v-row>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      class="pa-2 pl-4"
      v-for="save in rom.saves"
      :key="save.id"
      :title="save.file_name"
      :subtitle="`${save.emulator} - ${formatBytes(save.file_size_bytes)}`"
    >
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
        <v-btn
          icon
          @click="deleteSave(save)"
          rounded="0"
          variant="text"
          size="small"
          class="ml-1 bg-terciary"
        >
          <v-icon class="text-romm-red">mdi-delete</v-icon>
        </v-btn>
      </template>
    </v-list-item>
  </v-list>
</template>
