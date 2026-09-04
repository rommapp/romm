<script setup lang="ts">
// ManualUploadTargetDialog: asks whether an uploaded manual should live in the
// shared resources directory (sticks to the ROM in the database) or the ROM's
// folder on disk (visible to external tools).
import { RBtn, RDialog, RIcon } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import storeUpload from "@/stores/upload";
import type { Events } from "@/types/emitter";
import { useRomSync } from "@/v2/composables/useRomSync";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const { refetchRom } = useRomSync();
const uploadStore = storeUpload();

const TARGETS = {
  resources: {
    upload: romApi.uploadManuals,
    successKey: "rom.manuals-upload-success",
    skippedKey: "rom.manuals-upload-skipped",
  },
  folder: {
    upload: romApi.uploadManualFiles,
    successKey: "rom.manual-files-upload-success",
    skippedKey: "rom.manual-files-upload-skipped",
  },
} as const;

type UploadTarget = keyof typeof TARGETS;

const show = ref(false);
const rom = ref<DetailedRom | null>(null);
const files = ref<File[]>([]);

// Only ask when the destination is still open.
const handleShow = (payload: Events["showManualUploadTargetDialog"]) => {
  if (payload.rom.has_simple_single_file) {
    enqueue("resources", payload.rom, payload.files);
    return;
  }
  if (payload.rom.files?.some((file) => file.category === "manual")) {
    enqueue("folder", payload.rom, payload.files);
    return;
  }
  rom.value = payload.rom;
  files.value = payload.files;
  show.value = true;
};
emitter?.on("showManualUploadTargetDialog", handleShow);
onBeforeUnmount(() => emitter?.off("showManualUploadTargetDialog", handleShow));

async function handleUploadResult(
  responses: PromiseSettledResult<unknown>[],
  successKey: string,
  skippedKey: string,
  target: DetailedRom,
) {
  const successful = responses.filter((r) => r.status === "fulfilled").length;
  const failed = responses.length - successful;

  if (failed === 0) uploadStore.reset();

  if (successful > 0) {
    snackbar.success(t(successKey, { count: successful, failed }), {
      icon: "mdi-check-bold",
      timeout: 3000,
    });
    await refetchRom(target.id);
  } else {
    snackbar.warning(t(skippedKey), {
      icon: "mdi-close-circle",
      timeout: 5000,
    });
  }
}

async function uploadTo(
  target: UploadTarget,
  targetRom: DetailedRom,
  targetFiles: File[],
) {
  const { upload, successKey, skippedKey } = TARGETS[target];
  const responses = await upload({
    romId: targetRom.id,
    filesToUpload: targetFiles,
  });
  await handleUploadResult(responses, successKey, skippedKey, targetRom);
}

// Serialized so a drop mid-upload waits rather than replacing the one running.
let queue: Promise<void> = Promise.resolve();

function enqueue(
  target: UploadTarget,
  targetRom: DetailedRom,
  targetFiles: File[],
) {
  if (targetFiles.length === 0) return;
  queue = queue
    .catch(() => undefined)
    .then(() => uploadTo(target, targetRom, targetFiles));
}

function chooseTarget(target: UploadTarget) {
  const currentRom = rom.value;
  if (!currentRom) return;
  const pending = files.value;
  closeDialog();
  enqueue(target, currentRom, pending);
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
      <RBtn variant="text" @click="closeDialog">
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
