<script setup>
import { ref, inject } from "vue";

import { formatBytes } from "@/utils/utils";
import api from "@/services/api";
import storeRoms from "@/stores/roms";

const props = defineProps(["rom"]);
const statesToUpload = ref([]);
const emitter = inject("emitter");
const romsStore = storeRoms();

async function deleteState(state) {
  await api
    .deleteStates({
      states: [state],
    })
    .then(({ data }) => {
      props.rom.states = data;
      romsStore.update(props.rom);
    })
    .catch(({ response, message }) => {
      emitter.emit("snackbarShow", {
        msg: `Unable to delete state: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
}

async function uploadStates() {
  emitter.emit("snackbarShow", {
    msg: `Uploading ${statesToUpload.value.length} states to ${props.rom.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await api
    .uploadStates({
      states: statesToUpload.value,
      rom: props.rom,
    })
    .then(({ data }) => {
      const { states, uploaded } = data;
      props.rom.states = states;
      romsStore.update(props.rom);
      statesToUpload.value = [];

      emitter.emit("snackbarShow", {
        msg: `${uploaded} files uploaded successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch(({ response, message }) => {
      emitter.emit("snackbarShow", {
        msg: `Unable to upload states: ${
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
      @keyup.enter="uploadStates()"
      :label="`Upload state files for ${props.rom.name}`"
      v-model="statesToUpload"
      prepend-inner-icon="mdi-file"
      prepend-icon=""
      multiple
      chips
      required
      variant="outlined"
      hide-details
    />
    <v-btn @click="uploadStates()" class="text-romm-green ml-5 bg-terciary">
      Upload
    </v-btn>
  </v-row>
  <v-list rounded="0" class="pa-0">
    <v-list-item
      v-for="state in rom.states"
      :key="state.id"
      :title="state.file_name"
      :subtitle="`${state.emulator} - ${formatBytes(state.file_size_bytes)}`"
    >
      <template v-slot:append>
        <v-btn icon :href="state.download_path" download>
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn icon @click="deleteState(state)">
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </template>
    </v-list-item>
  </v-list>
</template>
