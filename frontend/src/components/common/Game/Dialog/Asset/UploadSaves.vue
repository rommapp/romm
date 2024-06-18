<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import saveApi from "@/services/api/save";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, nextTick, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { xs, mdAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const rom = ref<DetailedRom | null>(null);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("addSavesDialog", (selectedRom) => {
  rom.value = selectedRom;
  updateDataTablePages();
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
const page = ref(1);
const itemsPerPage = ref(10);
const pageCount = ref(0);
const PER_PAGE_OPTIONS = [10, 25, 50, 100];

// Functions
function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
  updateDataTablePages();
}

function removeFileFromFileInput(file: string) {
  filesToUpload.value = filesToUpload.value.filter((f) => f.name !== file);
  updateDataTablePages();
  if (filesToUpload.value.length == 0) {
    closeDialog();
  }
}

// TODO: make upload saves reactive
async function uploadSaves() {
  if (!rom.value) return;

  emitter?.emit("snackbarShow", {
    msg: `Uploading ${filesToUpload.value.length} saves to ${rom.value?.name}...`,
    icon: "mdi-loading mdi-spin",
    color: "romm-accent-1",
  });

  saveApi
    .uploadSaves({
      rom: rom.value,
      saves: filesToUpload.value,
    })
    .then(({ data }) => {
      const { saves, uploaded } = data;

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
  closeDialog();
}

function checkAddedFiles() {
  updateDataTablePages();
  if (filesToUpload.value.length == 0) {
    closeDialog();
  }
}

function closeDialog() {
  show.value = false;
  filesToUpload.value = [];
  rom.value = null;
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(filesToUpload.value.length / itemsPerPage.value);
}
watch(itemsPerPage, async () => {
  updateDataTablePages();
});
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-content-save"
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
          @keyup.enter="uploadSaves"
        />
        <v-data-table
          v-if="filesToUpload.length > 0"
          :item-value="(item) => item.name"
          :items="filesToUpload"
          :width="mdAndUp ? '60vw' : '95vw'"
          :items-per-page="itemsPerPage"
          :items-per-page-options="PER_PAGE_OPTIONS"
          :headers="HEADERS"
          v-model:page="page"
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
          <template #bottom>
            <v-divider />
            <v-row no-gutters class="pt-2 align-center justify-center">
              <v-col class="px-6">
                <v-pagination
                  v-model="page"
                  rounded="0"
                  :show-first-last-page="true"
                  active-color="romm-accent-1"
                  :length="pageCount"
                />
              </v-col>
              <v-col cols="5" sm="3" xl="2">
                <v-select
                  v-model="itemsPerPage"
                  class="pa-2"
                  label="Files per page"
                  density="compact"
                  variant="outlined"
                  :items="PER_PAGE_OPTIONS"
                  hide-details
                />
              </v-col>
            </v-row>
          </template>
        </v-data-table>
      </v-row>
    </template>

    <template #append>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            class="bg-terciary text-romm-green"
            :variant="
              filesToUpload.length == 0 || rom == null ? 'plain' : 'flat'
            "
            :disabled="filesToUpload.length == 0 || rom == null"
            @click="uploadSaves"
          >
            Upload
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
