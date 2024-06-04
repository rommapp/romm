<script setup lang="ts">
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import type { Emitter } from "mitt";
import firmwareApi from "@/services/api/firmware";
import { type Platform } from "@/stores/platforms";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";
import type { FirmwareSchema } from "@/__generated__";

const { xs, smAndUp, mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const selectedPlatform = ref<Platform | null>(null);
const selectedFirmware = ref<FirmwareSchema[]>([]);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showFirmwareDialog", (platform) => {
  selectedPlatform.value = platform;
  show.value = true;
});

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function removeFileFromList(file: string) {
  filesToUpload.value = filesToUpload.value.filter((f) => f.name !== file);
}

function closeDialog() {
  show.value = false;
  filesToUpload.value = [];
  selectedPlatform.value = null;
}

function uploadFirmware() {
  if (!selectedPlatform.value) return;

  firmwareApi
    .uploadFirmware({
      platformId: selectedPlatform.value.id,
      files: filesToUpload.value,
    })
    .then(({ data }) => {
      const { uploaded, firmware } = data;
      if (selectedPlatform.value) {
        selectedPlatform.value.firmware = firmware;
      }

      emitter?.emit("snackbarShow", {
        msg: `${uploaded} files uploaded successfully.`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 2000,
      });
    });

  filesToUpload.value = [];
}

function downloadFirmware() {
  selectedFirmware.value.map((firmware) => {
    const a = document.createElement("a");
    a.href = `/api/firmware/${firmware.id}/content/${firmware.file_name}`;
    a.download = `${firmware.file_name}`;
    a.click();
  });

  selectedFirmware.value = [];
}

function deleteFirmware() {
  firmwareApi
    .deleteFirmware({ firmware: selectedFirmware.value, deleteFromFs: false })
    .then(() => {
      if (selectedPlatform.value) {
        selectedPlatform.value.firmware =
          selectedPlatform.value.firmware?.filter(
            (firmware) => !selectedFirmware.value.includes(firmware)
          );
      }
      emitter?.emit("snackbarShow", {
        msg: "Firmware deleted successfully!",
        icon: "mdi-check-circle",
        color: "green",
        timeout: 4000,
      });
      selectedFirmware.value = [];
    });
}

function allFirmwareSelected() {
  if (selectedPlatform.value?.firmware?.length == 0) {
    return false;
  }
  return (
    selectedFirmware.value.length ===
    selectedPlatform.value?.firmware?.length
  );
}

function selectAllFirmware() {
  if (allFirmwareSelected()) {
    selectedFirmware.value = [];
  } else {
    selectedFirmware.value = selectedPlatform.value?.firmware ?? [];
  }
}
</script>

<template>
  <v-dialog
    :model-value="show"
    scroll-strategy="none"
    width="auto"
    :scrim="true"
    no-click-animation
    persistent
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card
      rounded="0"
      :class="{
        'edit-content': lgAndUp,
        'edit-content-tablet': mdAndDown,
        'edit-content-mobile': xs,
      }"
    >
      <v-toolbar
        density="compact"
        class="bg-terciary"
      >
        <v-row
          class="align-center"
          no-gutters
        >
          <v-col
            cols="9"
            sm="10"
            lg="11"
          >
            <v-icon
              icon="mdi-memory"
              class="ml-5"
            />
          </v-col>
          <v-col>
            <v-btn
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
              @click="closeDialog"
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider
        
        
      />

      <v-toolbar
        density="compact"
        class="bg-primary"
      >
        <v-row
          class="align-center"
          no-gutters
        >
          <v-col>
            <v-btn
              block
              icon=""
              class="text-romm-accent-1 bg-terciary"
              rounded="0"
              variant="text"
              @click="triggerFileInput"
            >
              <v-icon :class="{ 'mr-2': !xs }">
                mdi-plus
              </v-icon>
              <span v-if="!xs">Add firmware</span>
            </v-btn>
            <v-file-input
              id="file-input"
              v-model="filesToUpload"
              class="file-input"
              multiple
              required
              @keyup.enter="uploadFirmware()"
            />
          </v-col>
          <v-col
            cols="5"
            sm="3"
          >
            <v-btn
              block
              icon=""
              class="text-romm-green bg-terciary"
              rounded="0"
              variant="text"
              :disabled="filesToUpload.length == 0 || selectedPlatform == null"
              @click="uploadFirmware()"
            >
              <v-icon>mdi-upload</v-icon><span
                v-if="smAndUp"
                class="ml-2"
              >Upload</span>
            </v-btn>
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider
        
        
      />

      <v-card-text
        v-if="filesToUpload.length > 0"
        class="scroll bg-terciary py-2 px-8"
      >
        <v-row
          v-for="file in filesToUpload"
          :key="file.name"
          class="py-2 align-center"
          no-gutters
        >
          <v-col
            cols="6"
            sm="9"
          >
            <span>{{ file.name }}</span>
          </v-col>
          <v-col
            cols="4"
            sm="2"
          >
            [<span class="text-romm-accent-1">{{ formatBytes(file.size) }}</span>]
          </v-col>
          <v-col
            cols="2"
            sm="1"
          >
            <v-btn
              icon
              size="x-small"
              rounded="0"
              variant="text"
              class="pa-0 ma-0"
              @click="removeFileFromList(file.name)"
            >
              <v-icon class="text-romm-red">
                mdi-delete
              </v-icon>
            </v-btn>
          </v-col>
        </v-row>
      </v-card-text>

      <v-card-text
        v-if="
          selectedPlatform?.firmware != undefined &&
            selectedPlatform?.firmware?.length > 0
        "
        class="my-4 py-0"
      >
        <v-list
          rounded="0"
          class="pa-0"
        >
          <v-list-item
            v-for="firmware in selectedPlatform?.firmware ?? []"
            :key="firmware.id"
            class="px-3"
          >
            <template #prepend>
              <v-checkbox
                v-model="selectedFirmware"
                :value="firmware"
                color="romm-accent-1"
                hide-details
              />
            </template>
            <v-list-item-title class="pb-1">
              {{ firmware.file_name }}
              <v-chip
                v-if="firmware.is_verified"
                label
                size="x-small"
                variant="tonal"
                class="text-romm-green ml-2"
                title="Passed file size, SHA1 and MD5 checksum checks"
              >
                VERIFIED
              </v-chip>
            </v-list-item-title>
            <v-list-item-subtitle class="text-truncate mr-4">
              {{ formatBytes(firmware.file_size_bytes) }} -
              {{ firmware.md5_hash }}
            </v-list-item-subtitle>

            <template #append>
              <v-btn
                icon
                :href="`/api/firmware/${firmware.id}/content/${firmware.file_name}`"
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
      </v-card-text>

      <v-toolbar
        density="compact"
        class="bg-terciary"
      >
        <v-row
          class="align-center"
          no-gutters
        >
          <v-col
            cols="5"
            sm="3"
          >
            <v-btn
              class="bg-terciary ml-3"
              rounded="0"
              variant="text"
              :disabled="
                !(
                  selectedPlatform?.firmware != undefined &&
                  selectedPlatform?.firmware?.length > 0
                )
              "
              @click="selectAllFirmware()"
            >
              <v-icon class="pr-2">
                {{
                  allFirmwareSelected()
                    ? "mdi-checkbox-marked"
                    : "mdi-checkbox-blank-outline"
                }}
              </v-icon>
              <span v-if="smAndUp">{{
                allFirmwareSelected() ? "Unselect all" : "Select all"
              }}</span>
            </v-btn>
          </v-col>
          <v-col class="text-right">
            <v-btn
              :icon="!smAndUp ?? 'mdi-download'"
              :disabled="!selectedFirmware.length"
              rounded="0"
              variant="text"
              class="my-3 bg-terciary"
              @click="downloadFirmware()"
            >
              <v-icon>mdi-download</v-icon>
              <span
                v-if="smAndUp"
                class="ml-2"
              >Download</span>
            </v-btn>
            <v-btn
              :icon="!smAndUp ?? 'mdi-delete'"
              :disabled="!selectedFirmware.length"
              rounded="0"
              variant="text"
              class="my-3 mr-3 bg-terciary text-romm-red"
              @click="deleteFirmware()"
            >
              <v-icon>mdi-delete</v-icon>
              <span
                v-if="smAndUp"
                class="ml-2"
              >Delete</span>
            </v-btn>
          </v-col>
        </v-row>
      </v-toolbar>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.edit-content {
  width: 900px;
}

.edit-content-tablet {
  width: 570px;
}

.edit-content-mobile {
  width: 85vw;
}

</style>
