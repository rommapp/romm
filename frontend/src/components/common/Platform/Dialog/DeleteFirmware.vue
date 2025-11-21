<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import type { FirmwareSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import firmwareApi from "@/services/api/firmware";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { mdAndUp, lgAndUp, xs, smAndUp } = useDisplay();
const show = ref(false);
const firmwares = ref<FirmwareSchema[]>([]);
const firmwaresToDeleteFromFs = ref<number[]>([]);
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteFirmwareDialog", (firmwaresToDelete) => {
  firmwares.value = firmwaresToDelete;
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
          (firm) => !firmwares.value.includes(firm),
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
      console.error(error);
      emitter?.emit("snackbarShow", {
        msg: error.response.data.detail,
        icon: "mdi-close-circle",
        color: "red",
      });
      return;
    });
  closeDialog();
}

function closeDialog() {
  show.value = false;
  firmwaresToDeleteFromFs.value = [];
  firmwares.value = [];
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-delete"
    scroll-content
    :width="mdAndUp ? '60vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>Removing</span>
        <span class="text-primary mx-1">{{ firmwares.length }}</span>
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
      <v-data-table-virtual
        v-model="firmwaresToDeleteFromFs"
        :item-value="(item) => item.id"
        :items="firmwares"
        :width="mdAndUp ? '60vw' : '95vw'"
        :headers="HEADERS"
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
                <v-chip size="x-small" label>
                  {{ formatBytes(item.file_size_bytes) }}
                </v-chip>
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
            <template #append>
              <template v-if="lgAndUp">
                <v-chip size="x-small" label>
                  {{ formatBytes(item.file_size_bytes) }}
                </v-chip>
                <v-chip class="ml-1" color="blue" size="x-small" label>
                  <span class="text-truncate">{{ item.md5_hash }}</span>
                </v-chip>
              </template>
            </template>
          </v-list-item>
        </template>
      </v-data-table-virtual>
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
          <v-btn class="bg-toplayer" variant="flat" @click="closeDialog">
            Cancel
          </v-btn>
          <v-btn
            class="text-romm-red bg-toplayer"
            variant="flat"
            @click="deleteFirmware"
          >
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
