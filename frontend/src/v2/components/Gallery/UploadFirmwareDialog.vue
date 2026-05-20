<script setup lang="ts">
// UploadFirmwareDialog — RDialog mounted from FirmwareDrawer that
// collects firmware files and POSTs them to `firmwareApi.uploadFirmware`.
//
// Flow:
//   1. Open with empty file list — automatically triggers the native
//      file picker the first time the dialog mounts each open.
//   2. User picks one or more files; each row gets a size chip + a
//      per-row remove (✕) so they can prune the list before upload.
//   3. Cancel closes; Upload fires the multipart POST and emits
//      `uploaded` with the server's refreshed firmware array so the
//      parent drawer can sync state without a refetch.
//
// Errors surface via snackbar; the dialog stays open on failure so the
// user keeps their file picks for retry.
import { RBtn, RChip, RDialog, RIcon } from "@v2/lib";
import { nextTick, ref, watch } from "vue";
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
const files = ref<File[]>([]);
const uploading = ref(false);

// Each open trip: reset the list and pop the OS file picker so the
// user lands directly in their library. The native dialog is the
// fastest path to "add files" and the empty modal we'd show without it
// would be confusing.
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      files.value = [];
      nextTick(() => fileInputRef.value?.click());
    }
  },
);

function onPick(evt: Event) {
  const input = evt.target as HTMLInputElement;
  const picked = input.files ? Array.from(input.files) : [];
  if (!picked.length) {
    closeDialog();
    return;
  }
  files.value = picked;
  // Reset the input so re-selecting the same file fires `change` again.
  input.value = "";
}

function removeFile(name: string) {
  files.value = files.value.filter((f) => f.name !== name);
}

function triggerPicker() {
  fileInputRef.value?.click();
}

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
    :width="520"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("platform.upload-firmware", "Upload firmware") }}</span>
    </template>

    <template #content>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="r-v2-upload-fw__input"
        :aria-label="t('platform.upload-firmware', 'Upload firmware')"
        @change="onPick"
      />

      <div class="r-v2-upload-fw__body">
        <p class="r-v2-upload-fw__hint">
          Adding firmware to <strong>{{ platform.display_name }}</strong>
        </p>

        <ul v-if="files.length > 0" class="r-v2-upload-fw__list">
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

        <RBtn
          variant="outlined"
          surface
          prepend-icon="mdi-plus"
          @click="triggerPicker"
        >
          {{
            files.length > 0
              ? t("common.add-more", "Add more")
              : t("common.choose-files", "Choose files")
          }}
        </RBtn>
      </div>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="uploading" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
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
.r-v2-upload-fw__input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.r-v2-upload-fw__body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 4px 8px;
}

.r-v2-upload-fw__hint {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  line-height: 1.5;
}

.r-v2-upload-fw__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
  overflow: hidden;
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
