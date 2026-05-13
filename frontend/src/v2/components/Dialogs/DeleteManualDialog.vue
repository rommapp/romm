<script setup lang="ts">
// DeleteManualDialog — confirms removing the primary manual from a ROM or
// a single manual file (multi-manual ROMs). The emitter payload picks the
// scope.
import { RBtn, RDialog, RIcon } from "@v2/lib";
import axios from "axios";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
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
onBeforeUnmount(() => emitter?.off("showDeleteManualDialog", handleShow));

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
    snackbar.success(
      t(primary ? "rom.manual-removed" : "rom.manual-file-removed"),
      { icon: "mdi-check-bold" },
    );
    closeDialog();
  } catch (error: unknown) {
    snackbar.error(
      t(
        primary ? "rom.manual-remove-failed" : "rom.manual-file-remove-failed",
        { error: errorMessage(error) },
      ),
      { icon: "mdi-close-circle" },
    );
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
  <RDialog
    v-model="show"
    icon="mdi-delete-outline"
    width="440"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.delete-manual-confirm-title") }}</span>
    </template>
    <template #content>
      <div class="r-v2-del-manual">
        <div class="r-v2-del-manual__icon">
          <RIcon icon="mdi-file-document-remove-outline" size="32" />
        </div>
        <p class="r-v2-del-manual__body">
          {{ t("rom.delete-manual-confirm-body") }}
        </p>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" :disabled="deleting" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="error"
        prepend-icon="mdi-delete"
        :loading="deleting"
        :disabled="deleting"
        @click="deleteManual"
      >
        {{ t("rom.delete-manual-button") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-del-manual {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 12px;
  padding: 4px 4px 8px;
}

.r-v2-del-manual__icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 14%,
    transparent
  );
  color: var(--r-color-danger-fg);
  display: grid;
  place-items: center;
}

.r-v2-del-manual__body {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: 13px;
  line-height: 1.5;
  max-width: 340px;
}
</style>
