<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import firmwareApi from "@/services/api/firmware";
import storeRoms from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { t } = useI18n();
const { xs, mdAndUp } = useDisplay();
const show = ref(false);
const romsStore = storeRoms();
const { currentPlatform } = storeToRefs(romsStore);
const filesToUpload = ref<File[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("addFirmwareDialog", () => {
  show.value = true;
  nextTick(() => triggerFileInput());
});
const HEADERS = [
  {
    title: t("common.name"),
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

function uploadFirmware() {
  if (!currentPlatform.value) return;

  emitter?.emit("snackbarShow", {
    msg: t("platform.firmware-uploading", {
      count: filesToUpload.value.length,
      platform: currentPlatform.value.name,
    }),
    icon: "mdi-loading mdi-spin",
    color: "primary",
  });

  firmwareApi
    .uploadFirmware({
      platformId: currentPlatform.value.id,
      files: filesToUpload.value,
    })
    .then(({ data }) => {
      const { uploaded, firmware } = data;
      if (currentPlatform.value) {
        currentPlatform.value.firmware = firmware;
      }

      emitter?.emit("snackbarShow", {
        msg: t("platform.firmware-uploaded-successfully", { count: uploaded }),
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
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-memory"
    empty-state-type="firmware"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
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
              <v-row no-gutters>
                <v-col>{{ item.name }}</v-col>
              </v-row>
              <v-row v-if="xs" no-gutters>
                <v-col>
                  <v-chip class="ml-2" size="x-small" label>
                    {{ formatBytes(item.size) }}
                  </v-chip>
                </v-col>
              </v-row>
              <template #append>
                <v-chip v-if="!xs" class="ml-2" size="x-small" label>
                  {{ formatBytes(item.size) }}
                </v-chip>
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
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="filesToUpload.length == 0 || !currentPlatform"
            :variant="
              filesToUpload.length == 0 || !currentPlatform ? 'plain' : 'flat'
            "
            @click="uploadFirmware"
          >
            {{ t("common.upload") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
