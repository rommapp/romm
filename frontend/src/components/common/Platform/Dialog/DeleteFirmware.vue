<script setup lang="ts">
import type { FirmwareSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import firmwareApi from "@/services/api/firmware";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, watch } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndUp, lgAndUp, xs, smAndUp } = useDisplay();
const show = ref(false);
const firmwares = ref<FirmwareSchema[]>([]);
const firmwaresToDeleteFromFs = ref<number[]>([]);
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteFirmwareDialog", (firmwaresToDelete) => {
  firmwares.value = firmwaresToDelete;
  updateDataTablePages();
  show.value = true;
});
const HEADERS = [
  {
    title: "Firmware",
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

// Funtcions
// TODO: remove firmwares from platform dialog (now refresh is needed)
async function deleteFirmware() {
  await firmwareApi
    .deleteFirmware({
      firmware: firmwares.value,
      deleteFromFs: firmwaresToDeleteFromFs.value,
    })
    .then(() => {
      if (currentPlatform.value?.firmware) {
        currentPlatform.value.firmware = currentPlatform.value.firmware.filter(
          (firm) => !firmwares.value.includes(firm)
        );
      }
      emitter?.emit("snackbarShow", {
        msg: "Firmware deleted successfully!",
        icon: "mdi-check-circle",
        color: "green",
        timeout: 4000,
      });
    })
    .catch((error) => {
      console.log(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });
  closeDialog();
}

function updateDataTablePages() {
  pageCount.value = Math.ceil(firmwares.value.length / itemsPerPage.value);
}

watch(page, async () => {
  updateDataTablePages();
});

function closeDialog() {
  show.value = false;
  firmwaresToDeleteFromFs.value = [];
  firmwares.value = [];
}
</script>

<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="mdAndUp ? '60vw' : '95vw'"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>Removing</span>
        <span class="text-romm-accent-1 mx-1">{{ firmwares.length }}</span>
        <span>firmware files from RomM</span>
      </v-row>
    </template>
    <template #prepend>
      <v-list-item class="text-caption text-center">
        <span
          >Select the firmware files you want to remove from your filesystem,
          otherwise they will only be deleted from RomM database.</span
        >
      </v-list-item>
    </template>
    <template #content>
      <v-data-table
        :item-value="(item) => item.id"
        :items="firmwares"
        :width="mdAndUp ? '60vw' : '95vw'"
        :items-per-page="itemsPerPage"
        :items-per-page-options="PER_PAGE_OPTIONS"
        :headers="HEADERS"
        v-model="firmwaresToDeleteFromFs"
        v-model:page="page"
        show-select
      >
        <template #item.name="{ item }">
          <v-list-item class="px-0">
            <v-row no-gutters>
              <v-col>
                {{ item.file_name
                }}<v-chip
                  v-if="firmwaresToDeleteFromFs.includes(item.id) && smAndUp"
                  label
                  size="x-small"
                  class="text-romm-red ml-1"
                >
                  Removing from filesystem
                </v-chip>
              </v-col>
            </v-row>
            <v-row no-gutters>
              <v-col>
                <v-chip
                  v-if="firmwaresToDeleteFromFs.includes(item.id) && !smAndUp"
                  label
                  size="x-small"
                  class="text-romm-red"
                >
                  Removing from filesystem
                </v-chip>
              </v-col>
            </v-row>
            <v-row v-if="!lgAndUp" no-gutters>
              <v-col>
                <v-chip size="x-small" label>{{
                  formatBytes(item.file_size_bytes)
                }}</v-chip>
                <v-chip
                  color="blue"
                  size="x-small"
                  label
                  :class="{ 'ml-1': !xs }"
                >
                  <span class="text-truncate"> {{ item.md5_hash }}</span>
                </v-chip>
              </v-col>
            </v-row>
            <template> </template>
            <template #append>
              <template v-if="lgAndUp">
                <v-chip size="x-small" label>{{
                  formatBytes(item.file_size_bytes)
                }}</v-chip>
                <v-chip class="ml-1" color="blue" size="x-small" label>
                  <span class="text-truncate">{{ item.md5_hash }}</span>
                </v-chip>
              </template>
            </template>
          </v-list-item>
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
                label="Firmwares per page"
                density="compact"
                variant="outlined"
                :items="PER_PAGE_OPTIONS"
                hide-details
              />
            </v-col>
          </v-row>
        </template>
      </v-data-table>
    </template>
    <template #append>
      <v-row v-if="firmwaresToDeleteFromFs.length > 0" no-gutters>
        <v-col>
          <v-list-item class="text-center mt-2">
            <span class="text-romm-red text-body-1">WARNING:</span>
            <span class="text-body-2 ml-1">You are going to remove</span>
            <span class="text-romm-red text-body-1 ml-1">{{
              firmwaresToDeleteFromFs.length
            }}</span>
            <span class="text-body-2 ml-1"
              >firmwares from your filesystem. This action can't be
              reverted!</span
            >
          </v-list-item>
        </v-col>
      </v-row>
      <v-row class="justify-center my-2">
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog" variant="flat">
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-red bg-terciary"
            variant="flat"
            @click="deleteFirmware"
          >
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
