<script setup lang="ts">
// ManualUploadTargetDialog — asks the user whether an uploaded manual
// should live in the shared resources directory (sticks to the ROM in the
// database) or the ROM's folder on disk (visible to external tools). If
// the ROM is a simple single-file ROM we skip the dialog and default to
// resources, same as v1.
import { RBtn, RDialog, RIcon } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
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
onBeforeUnmount(() => emitter?.off("showManualUploadTargetDialog", handleShow));

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

  if (failed === 0) uploadStore.reset();

  if (successful > 0) {
    snackbar.success(t(successKey, { count: successful, failed }), {
      icon: "mdi-check-bold",
      timeout: 3000,
    });
    await refreshRom();
  } else {
    snackbar.warning(t(skippedKey), {
      icon: "mdi-close-circle",
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
      <span>{{ t("rom.manual-upload-target-title") }}</span>
    </template>
    <template #content>
      <div class="r-v2-upload-target">
        <button
          type="button"
          class="r-v2-upload-target__option"
          :disabled="uploading"
          @click="chooseTarget('resources')"
        >
          <div class="r-v2-upload-target__icon">
            <RIcon icon="mdi-database-edit-outline" size="22" />
          </div>
          <div class="r-v2-upload-target__text">
            <p class="r-v2-upload-target__title">
              {{ t("rom.manual-upload-target-resources-title") }}
            </p>
            <p class="r-v2-upload-target__desc">
              {{ t("rom.manual-upload-target-resources-desc") }}
            </p>
          </div>
          <RIcon
            icon="mdi-chevron-right"
            size="16"
            class="r-v2-upload-target__chev"
          />
        </button>
        <button
          type="button"
          class="r-v2-upload-target__option"
          :disabled="uploading"
          @click="chooseTarget('folder')"
        >
          <div class="r-v2-upload-target__icon">
            <RIcon icon="mdi-folder-plus-outline" size="22" />
          </div>
          <div class="r-v2-upload-target__text">
            <p class="r-v2-upload-target__title">
              {{ t("rom.manual-upload-target-folder-title") }}
            </p>
            <p class="r-v2-upload-target__desc">
              {{ t("rom.manual-upload-target-folder-desc") }}
            </p>
          </div>
          <RIcon
            icon="mdi-chevron-right"
            size="16"
            class="r-v2-upload-target__chev"
          />
        </button>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" :disabled="uploading" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-upload-target {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-upload-target__option {
  appearance: none;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  padding: 14px 16px;
  display: grid;
  grid-template-columns: 42px 1fr auto;
  gap: 14px;
  align-items: center;
  text-align: left;
  cursor: pointer;
  color: inherit;
  font-family: inherit;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-upload-target__option:hover:not(:disabled) {
  background: var(--r-color-surface);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 40%,
    transparent
  );
  transform: translateY(-1px);
}
.r-v2-upload-target__option:disabled {
  opacity: 0.5;
  cursor: progress;
}

.r-v2-upload-target__icon {
  width: 42px;
  height: 42px;
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  color: var(--r-color-brand-primary);
  display: grid;
  place-items: center;
}

.r-v2-upload-target__text {
  min-width: 0;
}
.r-v2-upload-target__title {
  margin: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-upload-target__desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--r-color-fg-secondary);
  line-height: 1.4;
}

.r-v2-upload-target__chev {
  color: var(--r-color-fg-muted);
}
.r-v2-upload-target__option:hover:not(:disabled) .r-v2-upload-target__chev {
  color: var(--r-color-brand-primary);
}
</style>
