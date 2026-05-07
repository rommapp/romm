<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();
const uploadStore = storeUpload();

const show = ref(false);
const rom = ref<DetailedRom | null>(null);
const files = ref<File[]>([]);
const uploading = ref(false);

const handleShow = (payload: Events["showManualUploadTargetDialog"]) => {
  rom.value = payload.rom;
  files.value = payload.files;
  if (payload.rom.has_simple_single_file) {
    void chooseTarget("resources");
    return;
  }
  show.value = true;
};
emitter?.on("showManualUploadTargetDialog", handleShow);

onBeforeUnmount(() => {
  emitter?.off("showManualUploadTargetDialog", handleShow);
});

async function refreshRom() {
  if (!rom.value) return;
  try {
    const { data } = await romApi.getRom({ romId: rom.value.id });
    romsStore.currentRom = data;
    romsStore.update(data);
  } catch (error) {
    console.error(error);
  }
}

async function handleUploadResult(
  responses: PromiseSettledResult<unknown>[],
  successKey: string,
  skippedKey: string,
) {
  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;

  if (failed === 0) {
    uploadStore.reset();
  }

  if (successful > 0) {
    emitter?.emit("snackbarShow", {
      msg: t(successKey, { count: successful, failed }),
      icon: "mdi-check-bold",
      color: "green",
      timeout: 3000,
    });
    await refreshRom();
  } else {
    emitter?.emit("snackbarShow", {
      msg: t(skippedKey),
      icon: "mdi-close-circle",
      color: "orange",
      timeout: 5000,
    });
  }
}

async function chooseTarget(target: "resources" | "folder") {
  if (!rom.value || uploading.value) return;
  const currentRom = rom.value;
  const pending = files.value;
  if (pending.length === 0) {
    closeDialog();
    return;
  }

  uploading.value = true;
  try {
    if (target === "resources") {
      const responses = await romApi.uploadManuals({
        romId: currentRom.id,
        filesToUpload: pending,
      });
      await handleUploadResult(
        responses,
        "rom.manuals-upload-success",
        "rom.manuals-upload-skipped",
      );
    } else {
      const responses = await romApi.uploadManualFiles({
        romId: currentRom.id,
        filesToUpload: pending,
      });
      await handleUploadResult(
        responses,
        "rom.manual-files-upload-success",
        "rom.manual-files-upload-skipped",
      );
    }
    closeDialog();
  } finally {
    uploading.value = false;
  }
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  files.value = [];
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-book-open-page-variant-outline"
    width="520"
    @close="closeDialog"
  >
    <template #header>
      <v-toolbar-title class="text-h6 ml-2">
        {{ t("rom.manual-upload-target-title") }}
      </v-toolbar-title>
    </template>
    <template #content>
      <v-list class="bg-transparent pa-4" lines="two">
        <v-list-item
          class="bg-toplayer rounded mb-2"
          :disabled="uploading"
          @click="chooseTarget('resources')"
        >
          <template #prepend>
            <v-icon class="mr-2">mdi-database-edit-outline</v-icon>
          </template>
          <v-list-item-title>
            {{ t("rom.manual-upload-target-resources-title") }}
          </v-list-item-title>
          <v-list-item-subtitle class="text-wrap">
            {{ t("rom.manual-upload-target-resources-desc") }}
          </v-list-item-subtitle>
        </v-list-item>
        <v-list-item
          class="bg-toplayer rounded"
          :disabled="uploading"
          @click="chooseTarget('folder')"
        >
          <template #prepend>
            <v-icon class="mr-2">mdi-folder-plus-outline</v-icon>
          </template>
          <v-list-item-title>
            {{ t("rom.manual-upload-target-folder-title") }}
          </v-list-item-title>
          <v-list-item-subtitle class="text-wrap">
            {{ t("rom.manual-upload-target-folder-desc") }}
          </v-list-item-subtitle>
        </v-list-item>
      </v-list>
    </template>
    <template #footer>
      <v-row class="justify-end pa-2" no-gutters>
        <v-btn variant="text" :disabled="uploading" @click="closeDialog">
          {{ t("common.cancel") }}
        </v-btn>
      </v-row>
    </template>
  </RDialog>
</template>
