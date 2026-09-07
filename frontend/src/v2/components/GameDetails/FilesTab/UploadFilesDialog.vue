<script setup lang="ts">
// UploadFilesDialog: pick a destination inside the ROM folder and the files
// to send there. The Files tab owns the upload, and closes the dialog first.
import {
  RBtn,
  RChip,
  RDialog,
  RDropzone,
  RForm,
  RIcon,
  RSelect,
  RTextField,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { formatBytes } from "@/utils";
import { relativeFolderPath, required } from "@/v2/utils/validation";

export interface UploadFolderOption {
  /** Folder path relative to the ROM root; "" is the root itself. */
  value: string;
  label: string;
}

const props = defineProps<{
  modelValue: boolean;
  folders: UploadFolderOption[];
  initialFolder: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: { folder: string; files: File[] }];
}>();

const { t } = useI18n();

const NEW_FOLDER = "__new__";

const destination = ref<string>(props.initialFolder);
const newFolder = ref("");
const files = ref<File[]>([]);
const formRef = ref<InstanceType<typeof RForm> | null>(null);
const filledDz = ref<InstanceType<typeof RDropzone> | null>(null);

const destinations = computed(() => [
  { value: "", title: t("rom.folder-root") },
  ...props.folders.map((f) => ({ value: f.value, title: f.label })),
  { value: NEW_FOLDER, title: t("rom.upload-new-folder") },
]);

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    destination.value = props.initialFolder;
    newFolder.value = "";
    files.value = [];
  },
);

function addFiles(picked: File[]) {
  const seen = new Set(files.value.map((f) => f.name));
  files.value = [...files.value, ...picked.filter((f) => !seen.has(f.name))];
}

function removeFile(name: string) {
  files.value = files.value.filter((f) => f.name !== name);
}

function close() {
  emit("update:modelValue", false);
}

async function submit() {
  if (files.value.length === 0) return;
  const result = await formRef.value?.validate();
  if (result && !result.valid) return;
  const folder =
    destination.value === NEW_FOLDER
      ? newFolder.value.trim().replace(/\/+$/, "")
      : destination.value;
  emit("submit", { folder, files: files.value });
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-folder-upload-outline"
    width="520"
    @update:model-value="emit('update:modelValue', $event)"
    @close="close"
  >
    <template #header>
      <span>{{ t("rom.upload-to-folder") }}</span>
    </template>
    <template #content>
      <RForm ref="formRef" class="r-v2-upload-files">
        <RSelect
          v-model="destination"
          :items="destinations"
          :label="t('rom.upload-destination')"
          hide-details
        />
        <RTextField
          v-if="destination === NEW_FOLDER"
          v-model="newFolder"
          :label="t('rom.folder-name')"
          :hint="t('rom.upload-new-folder-hint')"
          :rules="[required(), relativeFolderPath]"
          autocomplete="off"
        />
        <RDropzone
          v-if="files.length === 0"
          :title="t('common.dropzone-title')"
          :hint="t('common.dropzone-hint')"
          :active-title="t('common.dropzone-drag-over')"
          :input-label="t('common.upload')"
          multiple
          @files="addFiles"
        />
        <RDropzone
          v-else
          ref="filledDz"
          overlay
          :release-label="t('common.dropzone-drag-over')"
          :input-label="t('common.upload')"
          multiple
          @files="addFiles"
        >
          <div class="r-v2-upload-files__filled">
            <header class="r-v2-upload-files__head">
              <span>
                {{ t("common.upload-files-selected", { count: files.length }) }}
              </span>
              <RBtn
                variant="text"
                size="small"
                prepend-icon="mdi-plus"
                @click="filledDz?.open()"
              >
                {{ t("common.add") }}
              </RBtn>
            </header>
            <ul class="r-v2-upload-files__list">
              <li
                v-for="f in files"
                :key="f.name"
                class="r-v2-upload-files__row"
              >
                <RIcon icon="mdi-file-outline" size="14" />
                <span class="r-v2-upload-files__name">{{ f.name }}</span>
                <RChip size="x-small" variant="translucent">
                  {{ formatBytes(f.size) }}
                </RChip>
                <RBtn
                  variant="text"
                  size="x-small"
                  icon="mdi-close"
                  color="danger"
                  :aria-label="t('common.remove')"
                  @click="removeFile(f.name)"
                />
              </li>
            </ul>
          </div>
        </RDropzone>
      </RForm>
    </template>
    <template #footer>
      <RBtn variant="text" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-cloud-upload-outline"
        :disabled="files.length === 0"
        @click="submit"
      >
        {{ t("common.upload") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-upload-files {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-upload-files__filled {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.r-v2-upload-files__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
}

.r-v2-upload-files__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.r-v2-upload-files__row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.r-v2-upload-files__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
}
</style>
