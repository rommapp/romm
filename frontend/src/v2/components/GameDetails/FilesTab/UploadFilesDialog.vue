<script setup lang="ts">
// UploadFilesDialog: pick a destination inside the ROM folder and the files
// to send there. The Files tab owns the upload, and closes the dialog first.
import { RBtn, RDialog, RForm, RSelect, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import PendingFilesDropzone from "@/v2/components/shared/PendingFilesDropzone.vue";
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
        <PendingFilesDropzone
          v-model="files"
          :input-label="t('common.upload')"
        />
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
</style>
