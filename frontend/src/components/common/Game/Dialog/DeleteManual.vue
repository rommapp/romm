<script setup lang="ts">
import axios from "axios";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import RDialog from "@/components/common/RDialog.vue";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const romsStore = storeRoms();

const show = ref(false);
const rom = ref<DetailedRom | null>(null);
const isPrimary = ref(false);
const fileId = ref<number | undefined>(undefined);
const deleting = ref(false);

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

const handleShow = (payload: Events["showDeleteManualDialog"]) => {
  rom.value = payload.rom;
  isPrimary.value = payload.isPrimary;
  fileId.value = payload.fileId;
  show.value = true;
};
emitter?.on("showDeleteManualDialog", handleShow);

onBeforeUnmount(() => {
  emitter?.off("showDeleteManualDialog", handleShow);
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

async function deleteManual() {
  if (!rom.value || deleting.value) return;
  deleting.value = true;
  const romId = rom.value.id;
  const primary = isPrimary.value;
  try {
    if (primary) {
      await romApi.removeManual({ romId });
    } else if (fileId.value !== undefined) {
      await romApi.deleteManualFile({ romId, fileId: fileId.value });
    }
    await refreshRom();
    emitter?.emit("snackbarShow", {
      msg: t(primary ? "rom.manual-removed" : "rom.manual-file-removed"),
      icon: "mdi-check-bold",
      color: "green",
    });
    closeDialog();
  } catch (error: unknown) {
    emitter?.emit("snackbarShow", {
      msg: t(
        primary ? "rom.manual-remove-failed" : "rom.manual-file-remove-failed",
        { error: errorMessage(error) },
      ),
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    deleting.value = false;
  }
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  isPrimary.value = false;
  fileId.value = undefined;
}
</script>

<template>
  <RDialog v-model="show" icon="mdi-delete" width="420" @close="closeDialog">
    <template #header>
      <v-toolbar-title class="text-h6 ml-2">
        {{ t("rom.delete-manual-confirm-title") }}
      </v-toolbar-title>
    </template>
    <template #content>
      <v-card-text class="pa-4">
        <p class="text-body-2 text-medium-emphasis">
          {{ t("rom.delete-manual-confirm-body") }}
        </p>
      </v-card-text>
    </template>
    <template #footer>
      <v-row class="justify-end pa-2" no-gutters>
        <v-btn variant="text" :disabled="deleting" @click="closeDialog">
          {{ t("common.cancel") }}
        </v-btn>
        <v-btn
          class="text-romm-red ml-2"
          :loading="deleting"
          :disabled="deleting"
          @click="deleteManual"
        >
          {{ t("rom.delete-manual-button") }}
        </v-btn>
      </v-row>
    </template>
  </RDialog>
</template>
