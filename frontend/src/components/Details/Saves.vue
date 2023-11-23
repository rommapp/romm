<script setup>
import { ref, inject, onBeforeUnmount } from "vue";

import { formatBytes } from "@/utils/utils";
import api from "@/services/api";

const props = defineProps(["rom"]);
const savesToUpload = ref([]);
const emitter = inject("emitter");

async function uploadSaves() {
  emitter.emit("snackbarShow", {
    msg: `Uploading ${savesToUpload.value.length} saves to ${props.rom.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await api
    .uploadSaves({
      savesToUpload: savesToUpload.value,
      rom: props.rom,
    })
    .then(({ data }) => {
      const { uploaded_assets } = data;

      emitter.emit("snackbarShow", {
        msg: `${uploaded_assets.length} files uploaded successfully!`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    })
    .catch(({ response, message }) => {
      emitter.emit("snackbarShow", {
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
  <v-row class="pa-2" no-gutters>
    <v-file-input
      @keyup.enter="uploadSaves()"
      :label="`Upload ${props.rom.name} save files`"
      v-model="savesToUpload"
      prepend-inner-icon="mdi-file"
      prepend-icon=""
      multiple
      chips
      required
      variant="outlined"
      hide-details
    />
    <v-btn @click="uploadSaves()" class="text-romm-green ml-5 bg-terciary">
      Upload
    </v-btn>
  </v-row>
  uploaded_assets
  <v-list rounded="0" class="pa-0">
    <v-list-item
      v-for="save in rom.saves"
      :key="save.id"
      :title="save.file_name"
      :subtitle="formatBytes(save.file_size_bytes)"
    >
      <template v-slot:append>
        <v-btn icon :href="save.download_path" download>
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn icon disabled>
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </template>
    </v-list-item>
  </v-list>
</template>
