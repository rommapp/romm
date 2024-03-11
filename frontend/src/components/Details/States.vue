<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";

import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import stateApi from "@/services/api/state";
import storeRoms, { type Rom } from "@/stores/roms";

import type { StateSchema } from "@/__generated__";

const props = defineProps<{ rom: Rom }>();
const statesToUpload = ref<File[]>([]);
const selectedStates = ref<StateSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();

emitter?.on("romUpdated", (rom) => {
  if (rom?.id === props.rom.id) {
    props.rom.user_states = rom.user_states;
  }
});

async function downloasStates() {
  selectedStates.value.map((state) => {
    const a = document.createElement("a");
    a.href = state.download_path;
    a.download = `${state.file_name}`;
    a.click();
  });

  selectedStates.value = [];
}

async function uploadStates() {
  emitter?.emit("snackbarShow", {
    msg: `Uploading ${statesToUpload.value.length} states to ${props.rom.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await stateApi
    .uploadStates({
      states: statesToUpload.value,
      rom: props.rom,
    })
    .then(({ data }) => {
      const { states, uploaded } = data;
      props.rom.user_states = states;
      romsStore.update(props.rom);
      statesToUpload.value = [];

      emitter?.emit("snackbarShow", {
        msg: `Uploaded ${uploaded} files successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
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
  <v-row class="pa-2 align-center" no-gutters>
    <v-col>
      <v-list-item class="px-0">
        <v-file-input
          @keyup.enter="uploadStates()"
          label="Select state files..."
          v-model="statesToUpload"
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
            :disabled="!statesToUpload.length"
            @click="uploadStates()"
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
      class="pa-2 pl-4"
      v-for="state in rom.user_states"
      :key="state.id"
      :title="state.file_name"
      :subtitle="`${state.emulator || 'unknown'} - ${formatBytes(state.file_size_bytes)}`"
    >
      <template v-slot:prepend>
        <v-checkbox
          v-model="selectedStates"
          :value="state"
          color="romm-accent-1"
          hide-details
        />
      </template>
      <template v-slot:append>
        <v-btn
          rounded="0"
          variant="text"
          class="bg-terciary"
          size="small"
          icon
          :href="state.download_path"
          download
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
      </template>
    </v-list-item>
  </v-list>
  <v-btn
    :disabled="!selectedStates.length"
    @click="downloasStates()"
    rounded="0"
    variant="text"
    class="mt-3 mr-3 bg-terciary"
  >
    <v-icon>mdi-download</v-icon>
    Download
  </v-btn>
  <v-btn
    :disabled="!selectedStates.length"
    @click="emitter?.emit('showDeleteStatesDialog', { rom: props.rom, states: selectedStates })"
    rounded="0"
    variant="text"
    class="mt-3 bg-terciary text-romm-red"
  >
    <v-icon>mdi-delete</v-icon>
    Delete
  </v-btn>
</template>
