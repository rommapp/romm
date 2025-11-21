<script setup lang="ts">
import { useDropZone } from "@vueuse/core";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import RDialog from "@/components/common/RDialog.vue";
import platformApi from "@/services/api/platform";
import romApi from "@/services/api/rom";
import socket from "@/services/socket";
import storeHeartbeat from "@/stores/heartbeat";
import { type Platform } from "@/stores/platforms";
import storeScanning from "@/stores/scanning";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { formatBytes } from "@/utils";

const { t } = useI18n();
const { mdAndUp, smAndUp } = useDisplay();
const show = ref(false);
const filesToUpload = ref<File[]>([]);
const scanningStore = storeScanning();
const selectedPlatform = ref<Platform | null>(null);
const supportedPlatforms = ref<Platform[]>();
const heartbeat = storeHeartbeat();
const uploadStore = storeUpload();
const dropZoneRef = ref<HTMLDivElement>();

const HEADERS = [
  {
    title: "Name",
    align: "start",
    sortable: true,
    key: "name",
  },
  { title: "", align: "end", key: "actions", sortable: false },
] as const;

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showUploadRomDialog", (platformWhereUpload) => {
  if (platformWhereUpload) {
    selectedPlatform.value = platformWhereUpload;
  }
  show.value = true;
  platformApi
    .getSupportedPlatforms()
    .then(({ data }) => {
      supportedPlatforms.value = data.sort((a, b) => {
        return a.name.localeCompare(b.name);
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload roms: ${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
});

async function uploadRoms() {
  if (!selectedPlatform.value) return;
  show.value = false;

  if (selectedPlatform.value.id == -1) {
    await platformApi
      .uploadPlatform({ fsSlug: selectedPlatform.value.fs_slug })
      .then(({ data }) => {
        emitter?.emit("snackbarShow", {
          msg: `Platform ${selectedPlatform.value?.name} created successfully!`,
          icon: "mdi-check-bold",
          color: "green",
          timeout: 2000,
        });
        selectedPlatform.value = data;
      })
      .catch((error) => {
        console.error(error);
        emitter?.emit("snackbarShow", {
          msg: error.response.data.detail,
          icon: "mdi-close-circle",
          color: "red",
        });
        return;
      })
      .finally(() => {
        emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
      });
  }

  const platformId = selectedPlatform.value.id;

  await romApi
    .uploadRoms({
      filesToUpload: filesToUpload.value,
      platformId: platformId,
    })
    .then((responses: PromiseSettledResult<unknown>[]) => {
      const successfulUploads = responses.filter(
        (d) => d.status == "fulfilled",
      );
      const failedUploads = responses.filter((d) => d.status == "rejected");

      if (failedUploads.length == 0) {
        uploadStore.reset();
      }

      if (successfulUploads.length == 0) {
        return emitter?.emit("snackbarShow", {
          msg: `All files skipped, nothing to upload.`,
          icon: "mdi-close-circle",
          color: "orange",
          timeout: 5000,
        });
      }

      emitter?.emit("snackbarShow", {
        msg: `${successfulUploads.length} files uploaded successfully (and ${failedUploads.length} skipped/failed). Starting scan...`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 3000,
      });

      scanningStore.setScanning(true);

      if (!socket.connected) socket.connect();
      setTimeout(() => {
        socket.emit("scan", {
          platforms: [platformId],
          type: "quick",
          apis: heartbeat.getEnabledMetadataOptions().map((s) => s.value),
        });
      }, 2000);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to upload roms: ${response?.data?.detail || response?.statusText || message}`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 4000,
      });
    });
  filesToUpload.value = [];
  selectedPlatform.value = null;
}

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function handleFileInputChange(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    const newFiles = Array.from(target.files);
    // Add new files to existing list, avoiding duplicates
    const uniqueNewFiles = newFiles.filter(
      (newFile) =>
        !filesToUpload.value.some(
          (existingFile) => existingFile.name === newFile.name,
        ),
    );
    filesToUpload.value = [...filesToUpload.value, ...uniqueNewFiles];
  }
  // Clear the input so the same files can be selected again if needed
  target.value = "";
}

function removeRomFromList(romName: string) {
  filesToUpload.value = filesToUpload.value.filter(
    (rom) => rom.name !== romName,
  );
}

function closeDialog() {
  show.value = false;
  filesToUpload.value = [];
  selectedPlatform.value = null;
}

function onDrop(files: File[] | null) {
  if (files && files.length > 0) {
    // Add new files to existing list, avoiding duplicates
    const newFiles = files.filter(
      (newFile) =>
        !filesToUpload.value.some(
          (existingFile) => existingFile.name === newFile.name,
        ),
    );
    filesToUpload.value = [...filesToUpload.value, ...newFiles];
  }
}

const { isOverDropZone } = useDropZone(dropZoneRef, {
  onDrop,
  multiple: true,
  preventDefaultForUnhandled: true,
});
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-cloud-upload-outline"
    :width="mdAndUp ? '40vw' : '95vw'"
    scroll-content
    @close="closeDialog"
  >
    <template #toolbar>
      <v-row class="align-center" no-gutters>
        <v-col>
          <v-autocomplete
            v-model="selectedPlatform"
            :label="t('common.platform')"
            item-title="name"
            :items="supportedPlatforms"
            return-object
            clearable
            single-line
            hide-details
          >
            <template #item="{ props, item }">
              <v-list-item
                class="py-2"
                v-bind="props"
                :title="item.raw.name ?? ''"
              >
                <template #prepend>
                  <PlatformIcon
                    :key="item.raw.slug"
                    :size="35"
                    :name="item.raw.name"
                    :slug="item.raw.slug"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
              </v-list-item>
            </template>
            <template #selection="{ item }">
              <v-list-item class="px-0" :title="item.raw.name ?? ''">
                <template #prepend>
                  <PlatformIcon
                    :key="item.raw.slug"
                    :size="35"
                    :slug="item.raw.slug"
                    :name="item.raw.name"
                    :fs-slug="item.raw.fs_slug"
                  />
                </template>
              </v-list-item>
            </template>
          </v-autocomplete>
        </v-col>
      </v-row>
    </template>
    <template #content>
      <!-- Dropzone Area -->
      <div
        ref="dropZoneRef"
        class="dropzone-container min-h-[200px] rounded-lg transition-all duration-300 ease-in-out ma-3"
        :class="{
          'dropzone-active': isOverDropZone,
          'dropzone-has-files': filesToUpload.length > 0,
        }"
      >
        <!-- Dropzone Visual Feedback -->
        <div
          v-if="filesToUpload.length === 0"
          class="flex flex-col items-center justify-center h-full min-h-[250px] p-8 text-center transition-all duration-300 ease-in-out"
        >
          <v-icon
            :class="{ 'animate-pulse-glow': isOverDropZone }"
            size="48"
            color="primary"
            class="transition-all duration-300 ease-in-out"
          >
            {{
              isOverDropZone ? "mdi-cloud-upload" : "mdi-cloud-upload-outline"
            }}
          </v-icon>
          <h3 class="text-h6 mt-4 mb-2">
            {{
              isOverDropZone
                ? t("common.dropzone-drag-over")
                : t("common.dropzone-title")
            }}
          </h3>
          <p class="text-body-2 text-medium-emphasis mb-4">
            {{ t("common.dropzone-description") }}
          </p>
          <v-btn color="primary" variant="outlined" @click="triggerFileInput">
            <v-icon start> mdi-plus </v-icon>
            {{ t("common.add") }}
          </v-btn>
        </div>

        <!-- Files List -->
        <div v-if="filesToUpload.length > 0" class="p-4">
          <div class="d-flex align-center justify-space-between mb-3">
            <h4 class="text-h6">
              {{
                t("common.upload-files-selected", {
                  count: filesToUpload.length,
                })
              }}
            </h4>
            <v-btn
              color="primary"
              variant="outlined"
              size="small"
              @click="triggerFileInput"
            >
              <v-icon start> mdi-plus </v-icon>
              {{ t("common.add") }}
            </v-btn>
          </div>

          <v-data-table-virtual
            :item-value="(item: File) => item.name"
            :items="filesToUpload"
            :headers="HEADERS"
            hide-default-header
            class="elevation-1"
          >
            <template #item.name="{ item }">
              <v-list-item class="pa-0">
                <v-row no-gutters>
                  <v-col>
                    {{ item.name }}
                  </v-col>
                </v-row>
                <v-row v-if="!smAndUp" no-gutters>
                  <v-col>
                    <v-chip size="x-small" label>
                      {{ formatBytes(item.size) }}
                    </v-chip>
                  </v-col>
                </v-row>
                <template #append>
                  <v-chip v-if="smAndUp" class="ml-2" size="x-small" label>
                    {{ formatBytes(item.size) }}
                  </v-chip>
                </template>
              </v-list-item>
            </template>
            <template #item.actions="{ item }">
              <v-btn @click="removeRomFromList(item.name)">
                <v-icon class="text-romm-red"> mdi-close </v-icon>
              </v-btn>
            </template>
          </v-data-table-virtual>
        </div>

        <!-- Hidden file input -->
        <input
          id="file-input"
          type="file"
          multiple
          class="opacity-0 pointer-events-none"
          style="display: none"
          @change="handleFileInputChange"
        />
      </div>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            class="bg-toplayer text-romm-green"
            :disabled="filesToUpload.length == 0 || selectedPlatform == null"
            :variant="
              filesToUpload.length == 0 || selectedPlatform == null
                ? 'plain'
                : 'flat'
            "
            @click="uploadRoms"
          >
            {{ t("common.upload") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>

<style scoped>
.dropzone-container {
  border: 2px dashed rgba(var(--v-theme-primary), 0.3);
}

.dropzone-container.dropzone-active {
  border: 2px dashed rgba(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.05);
}

.dropzone-container.dropzone-has-files {
  border: none;
  background-color: rgba(var(--v-theme-surface), 0.5);
}

.animate-pulse-glow {
  animation: pulse-glow 1.5s ease-in-out infinite;
}

@keyframes pulse-glow {
  0% {
    transform: scale(1);
    filter: brightness(1) drop-shadow(0 0 0 rgba(var(--v-theme-primary), 0));
  }
  50% {
    transform: scale(1.1);
    filter: brightness(1.2)
      drop-shadow(0 0 20px rgba(var(--v-theme-primary), 0.6));
  }
  100% {
    transform: scale(1);
    filter: brightness(1) drop-shadow(0 0 0 rgba(var(--v-theme-primary), 0));
  }
}
</style>
