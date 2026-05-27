<script setup lang="ts">
// UploadFirmwareDialog — RDialog mounted from FirmwareTab that
// collects firmware files and POSTs them to `firmwareApi.uploadFirmware`.
//
// Visual + interaction language mirrors the Upload view: dashed
// drop-zone with an empty state, switching to a file list once the
// user has picked anything. Cancel sits on the left of the footer,
// the primary Upload CTA on the right (matches the Upload view's
// gravity — destructive / dismiss actions away from the primary).
//
// Errors surface via snackbar; the dialog stays open on failure so
// the user keeps their file picks for retry.
import { RBtn, RChip, RDialog, RIcon } from "@v2/lib";
import { useDropZone } from "@vueuse/core";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { FirmwareSchema } from "@/__generated__";
import firmwareApi from "@/services/api/firmware";
import type { Platform } from "@/stores/platforms";
import { formatBytes } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  platform: Platform;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "uploaded", firmware: FirmwareSchema[]): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();

const fileInputRef = ref<HTMLInputElement | null>(null);
const dropZoneRef = ref<HTMLElement | null>(null);
const files = ref<File[]>([]);
const uploading = ref(false);

// Clear picks each time the dialog opens so a previous half-finished
// session doesn't bleed into the next. No auto-open of the OS picker
// — the drop zone is the primary affordance now, the native picker is
// secondary and on-demand.
watch(
  () => props.modelValue,
  (open) => {
    if (open) files.value = [];
  },
);

function addFiles(picked: File[]) {
  if (!picked.length) return;
  // De-dupe by name — matches the Upload view's behaviour.
  const seen = new Set(files.value.map((f) => f.name));
  const fresh = picked.filter((f) => !seen.has(f.name));
  if (fresh.length > 0) {
    files.value = [...files.value, ...fresh];
  }
}

function onPick(evt: Event) {
  const input = evt.target as HTMLInputElement;
  addFiles(input.files ? Array.from(input.files) : []);
  // Reset the input so re-selecting the same file fires `change` again.
  input.value = "";
}

function triggerPicker() {
  fileInputRef.value?.click();
}

function removeFile(name: string) {
  files.value = files.value.filter((f) => f.name !== name);
}

const { isOverDropZone } = useDropZone(dropZoneRef, {
  onDrop(picked: File[] | null) {
    if (picked) addFiles(picked);
  },
  multiple: true,
  preventDefaultForUnhandled: true,
});

function closeDialog() {
  emit("update:modelValue", false);
  files.value = [];
}

async function upload() {
  if (!files.value.length) return;
  uploading.value = true;
  try {
    const { firmware, uploaded } = await firmwareApi.uploadFirmware({
      platformId: props.platform.id,
      files: files.value,
    });
    snackbar.success(
      t("platform.firmware-uploaded-successfully", { count: uploaded }),
      { icon: "mdi-check-bold" },
    );
    emit("uploaded", firmware);
    closeDialog();
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      `Failed to upload firmware: ${
        e?.response?.data?.detail || e?.message || "unknown error"
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-memory"
    :width="560"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("platform.upload-firmware") }}</span>
    </template>

    <template #content>
      <div class="r-v2-upload-fw">
        <i18n-t
          keypath="platform.adding-firmware"
          tag="p"
          class="r-v2-upload-fw__hint"
        >
          <template #platform>
            <strong>{{ platform.display_name }}</strong>
          </template>
        </i18n-t>

        <input
          ref="fileInputRef"
          type="file"
          multiple
          class="r-v2-upload-fw__input"
          :aria-label="t('platform.upload-firmware')"
          @change="onPick"
        />

        <!-- Drop zone — empty state when no files, switches to a file
             list when populated. Matches the Upload view's visual
             vocabulary (dashed primary border, brand glow on drag,
             solid border once filled). -->
        <div
          ref="dropZoneRef"
          class="r-v2-upload-fw__dropzone"
          :class="{
            'r-v2-upload-fw__dropzone--active': isOverDropZone,
            'r-v2-upload-fw__dropzone--filled': files.length > 0,
          }"
        >
          <div v-if="files.length === 0" class="r-v2-upload-fw__empty">
            <RIcon
              :icon="
                isOverDropZone ? 'mdi-cloud-upload' : 'mdi-cloud-upload-outline'
              "
              size="40"
              color="primary"
              :class="{ 'r-v2-upload-fw__icon--pulse': isOverDropZone }"
            />
            <h3 class="r-v2-upload-fw__empty-title">
              {{
                isOverDropZone
                  ? t("common.dropzone-drag-over", "Release to upload")
                  : t("common.dropzone-title", "Drop files here")
              }}
            </h3>
            <p class="r-v2-upload-fw__empty-hint">
              {{
                t(
                  "platform.firmware-dropzone-description",
                  "Drag and drop firmware files here, or click to browse",
                )
              }}
            </p>
            <RBtn
              variant="outlined"
              color="primary"
              prepend-icon="mdi-plus"
              @click="triggerPicker"
            >
              {{ t("common.add", "Add files") }}
            </RBtn>
          </div>

          <div v-else class="r-v2-upload-fw__filled">
            <header class="r-v2-upload-fw__filled-head">
              <span>
                {{ t("common.upload-files-selected", { count: files.length }) }}
              </span>
              <RBtn
                variant="text"
                size="small"
                prepend-icon="mdi-plus"
                @click="triggerPicker"
              >
                {{ t("common.add", "Add") }}
              </RBtn>
            </header>
            <ul class="r-v2-upload-fw__list">
              <li v-for="f in files" :key="f.name" class="r-v2-upload-fw__row">
                <RIcon icon="mdi-file-outline" size="14" />
                <span class="r-v2-upload-fw__row-name">{{ f.name }}</span>
                <RChip size="x-small" variant="translucent">
                  {{ formatBytes(f.size) }}
                </RChip>
                <RBtn
                  variant="text"
                  size="x-small"
                  icon="mdi-close"
                  color="danger"
                  :aria-label="t('common.remove', 'Remove')"
                  @click="removeFile(f.name)"
                />
              </li>
            </ul>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="uploading" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <span class="r-v2-upload-fw__footer-spacer" />
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-cloud-upload-outline"
        :disabled="files.length === 0"
        :loading="uploading"
        @click="upload"
      >
        {{ t("common.upload") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-upload-fw {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px;
}

.r-v2-upload-fw__hint {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  line-height: 1.5;
}

.r-v2-upload-fw__input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

/* Pushes the Upload CTA to the trailing edge of the footer flex row
   while Cancel stays anchored at the leading edge. Matches the
   primary-action-right convention used across v2 dialogs. */
.r-v2-upload-fw__footer-spacer {
  flex: 1;
}

/* ── Drop zone ────────────────────────────────────────────────────
   Dashed primary border that brightens on hover-with-files and goes
   solid when the user actually drags over the zone. Mirrors the
   Upload view's vocabulary. */
.r-v2-upload-fw__dropzone {
  position: relative;
  min-height: 220px;
  border: 2px dashed
    color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
  border-radius: var(--r-radius-lg);
  background: var(--r-color-bg-elevated);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-upload-fw__dropzone--active {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}
.r-v2-upload-fw__dropzone--filled {
  border-style: solid;
  border-color: var(--r-color-border-strong);
}

/* ── Empty state ─────────────────────────────────────────────── */
.r-v2-upload-fw__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 220px;
  padding: 24px 16px;
  text-align: center;
}
.r-v2-upload-fw__empty-title {
  margin: 6px 0 0;
  font-size: 15px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-upload-fw__empty-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--r-color-fg-muted);
  max-width: 320px;
  line-height: 1.5;
}
.r-v2-upload-fw__icon--pulse {
  animation: r-v2-upload-fw-pulse 1.4s ease-in-out infinite;
}
@keyframes r-v2-upload-fw-pulse {
  50% {
    transform: scale(1.12);
    filter: drop-shadow(
      0 0 12px color-mix(in srgb, var(--r-color-brand-primary) 60%, transparent)
    );
  }
}

/* ── Filled state ────────────────────────────────────────────── */
.r-v2-upload-fw__filled {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.r-v2-upload-fw__filled-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-upload-fw__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
  overflow: hidden;
  max-height: 260px;
  overflow-y: auto;
}

.r-v2-upload-fw__row {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--r-color-fg);
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-upload-fw__row:last-child {
  border-bottom: 0;
}
.r-v2-upload-fw__row-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
