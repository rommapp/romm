<script setup lang="ts">
import RDialog from "@/components/common/Dialog.vue";
import firmwareApi from "@/services/api/firmware";
import storePlatforms, { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { inject, nextTick, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const platform = ref<Platform | null>(null);
const platforms = storePlatforms();
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("addFirmwareDialog", (selectedPlatform) => {
  platform.value = selectedPlatform;
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
const firmwareToUploadPage = ref(1);
const firmwareToUploadPerPage = ref(10);
const firmwareToUploadPageCount = ref(0);
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

function uploadFirmware() {
  if (!platform.value) return;

  firmwareApi
    .uploadFirmware({
      platformId: platform.value.id,
      files: filesToUpload.value,
    })
    .then(({ data }) => {
      const { uploaded, firmware } = data;
      if (platform.value) {
        platform.value.firmware = firmware;
      }

      emitter?.emit("snackbarShow", {
        msg: `${uploaded} files uploaded successfully.`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    });

  filesToUpload.value = [];
  updateDataTablePages();
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
  platform.value = null;
}

function updateDataTablePages() {
  firmwareToUploadPageCount.value = Math.ceil(
    filesToUpload.value.length / firmwareToUploadPerPage.value
  );
}
watch(firmwareToUploadPerPage, async () => {
  updateDataTablePages();
});
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
          @keyup.enter="uploadFirmware"
        />
        <v-data-table
          v-if="filesToUpload.length > 0"
          :item-value="(item) => item.name"
          :items="filesToUpload"
          :width="mdAndUp ? '60vw' : '95vw'"
          :items-per-page="firmwareToUploadPerPage"
          :items-per-page-options="PER_PAGE_OPTIONS"
          :headers="HEADERS"
          v-model:page="firmwareToUploadPage"
          hide-default-header
        >
          <template #item.name="{ item }">
            <v-list-item class="px-0">
              <v-row no-gutters
                ><v-col>{{ item.name }}</v-col></v-row
              >
              <template #append>
                <v-chip class="ml-2" size="x-small" label>{{
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
                  v-model="firmwareToUploadPage"
                  rounded="0"
                  :show-first-last-page="true"
                  active-color="romm-accent-1"
                  :length="firmwareToUploadPageCount"
                />
              </v-col>
              <v-col cols="5" sm="3" xl="2">
                <v-select
                  v-model="firmwareToUploadPerPage"
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
          <v-btn class="bg-terciary" @click="closeDialog">
            Cancel
          </v-btn>
          <v-btn
            class="bg-terciary"
            :disabled="filesToUpload.length == 0 || platform == null"
            @click="uploadFirmware()"
          >
            <span
              :class="{
                'text-romm-green': !(
                  filesToUpload.length == 0 || platform == null
                ),
              }"
              >Upload</span
            >
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
