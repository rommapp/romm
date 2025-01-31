<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import stateApi from "@/services/api/state";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, nextTick, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs, mdAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const rom = ref<DetailedRom | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("addStatesDialog", (selectedRom) => {
  rom.value = selectedRom;
  show.value = true;
  nextTick(() => triggerFileInput());
});
const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function removeFileFromFileInput(file: string) {
  filesToUpload.value = filesToUpload.value.filter((f) => f.name !== file);
  if (filesToUpload.value.length == 0) {
    closeDialog();
  }
}

// TODO: make upload states reactive
function uploadStates() {
  if (!rom.value) return;

  emitter?.emit("snackbarShow", {
    msg: `Uploading ${filesToUpload.value.length} states to ${rom.value?.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "primary",
  });

  stateApi
    .uploadStates({
      rom: rom.value,
      states: filesToUpload.value,
    })
    .then(({ data }) => {
      const { states, uploaded } = data;

      emitter?.emit("snackbarShow", {
        msg: `${uploaded} files uploaded successfully.`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    });

  closeDialog();
}

function checkAddedFiles() {
  if (filesToUpload.value.length == 0) {
    closeDialog();
  }
}

function closeDialog() {
  show.value = false;
  filesToUpload.value = [];
  rom.value = null;
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-memory"
    empty-state-type="firmware"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center" no-gutters>
        <v-file-input
          id="file-input"
          v-model="filesToUpload"
          class="file-input"
          multiple
          required
          @update:model-value="checkAddedFiles"
          @keyup.enter="uploadStates"
        />
        <v-data-table-virtual
          v-if="filesToUpload.length > 0"
          :item-value="(item) => item.name"
          :items="filesToUpload"
          :width="mdAndUp ? '60vw' : '95vw'"
          :headers="HEADERS"
          hide-default-header
        >
          <template #item.name="{ item }">
            <v-list-item class="px-0">
              <v-row no-gutters
                ><v-col>{{ item.name }}</v-col></v-row
              >
              <v-row v-if="xs" no-gutters>
                <v-col>
                  <v-chip class="ml-2" size="x-small" label>{{
                    formatBytes(item.size)
                  }}</v-chip>
                </v-col>
              </v-row>
              <template #append>
                <v-chip v-if="!xs" class="ml-2" size="x-small" label>{{
                  formatBytes(item.size)
                }}</v-chip>
              </template>
            </v-list-item>
          </template>
          <template #item.actions="{ item }">
            <v-btn-group divided density="compact">
              <v-btn @click="removeFileFromFileInput(item.name)">
                <v-icon class="text-romm-red"> mdi-close </v-icon>
              </v-btn>
            </v-btn-group>
          </template>
        </v-data-table-virtual>
      </v-row>
    </template>

    <template #append>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :variant="
              filesToUpload.length == 0 || rom == null ? 'plain' : 'flat'
            "
            :disabled="filesToUpload.length == 0 || rom == null"
            @click="uploadStates"
          >
            Upload
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
