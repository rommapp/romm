<script setup lang="ts">
import type { SaveSchema } from "@/__generated__";
import saveApi from "@/services/api/save";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

const props = defineProps<{ rom: DetailedRom }>();
const romRef = ref<DetailedRom>(props.rom);
const savesToUpload = ref<File[]>([]);
const selectedSaves = ref<SaveSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();

emitter?.on("romUpdated", (rom) => {
  if (rom?.id === romRef.value.id) {
    romRef.value.user_saves = rom.user_saves;
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
    msg: `Uploading ${savesToUpload.value.length} saves to ${romRef.value.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  await saveApi
    .uploadSaves({
      saves: savesToUpload.value,
      rom: romRef.value,
    })
    .then(({ data }) => {
      const { saves, uploaded } = data;
      romRef.value.user_saves = saves;
      romsStore.update(romRef.value);
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
  <v-row
    class="pa-2 align-center"
    no-gutters
  >
    <v-col>
      <v-list-item class="px-0">
        <v-file-input
          v-model="savesToUpload"
          label="Select save files..."
          prepend-inner-icon="mdi-file"
          prepend-icon=""
          multiple
          chips
          required
          variant="outlined"
          density="compact"
          hide-details
          @keyup.enter="uploadSaves()"
        />
        <template #append>
          <v-btn
            :disabled="!savesToUpload.length"
            class="text-romm-green ml-3 bg-terciary"
            @click="uploadSaves()"
          >
            Upload
          </v-btn>
        </template>
      </v-list-item>
    </v-col>
  </v-row>
  <v-list
    rounded="0"
    class="pa-0"
  >
    <v-list-item
      v-for="save in rom.user_saves"
      :key="save.id"
      class="px-3"
      :title="save.file_name"
      :subtitle="`${save.emulator || 'unknown'} - ${formatBytes(
        save.file_size_bytes
      )}`"
    >
      <template #prepend>
        <v-checkbox
          v-model="selectedSaves"
          :value="save"
          color="romm-accent-1"
          hide-details
        />
      </template>
      <template #append>
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
    rounded="0"
    variant="text"
    class="mt-3 mr-3 bg-terciary"
    @click="downloadSaves()"
  >
    <v-icon>mdi-download</v-icon>
    Download
  </v-btn>
  <v-btn
    :disabled="!selectedSaves.length"
    rounded="0"
    variant="text"
    class="mt-3 bg-terciary text-romm-red"
    @click="
      emitter?.emit('showDeleteSavesDialog', {
        rom: props.rom,
        saves: selectedSaves,
      })
    "
  >
    <v-icon>mdi-delete</v-icon>
    Delete
  </v-btn>
</template>
