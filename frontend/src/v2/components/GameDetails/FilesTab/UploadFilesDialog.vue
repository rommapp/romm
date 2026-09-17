<script setup lang="ts">
// UploadFilesDialog: pick a destination inside the ROM folder and the files
// to send there. The Files tab owns the upload, and closes the dialog first.
import { RBtn, RDialog, RForm, RIcon, RSelect, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import PendingFilesDropzone from "@/v2/components/shared/PendingFilesDropzone.vue";
import { relativeFolderPath, required } from "@/v2/utils/validation";

export interface UploadFolderOption {
  /** Folder path relative to the ROM root; "" is the root itself. */
  value: string;
  label: string;
  icon: string;
}

const props = defineProps<{
  modelValue: boolean;
  /** Every destination to offer, the root included. */
  folders: UploadFolderOption[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: { folder: string; files: File[] }];
}>();

const { t } = useI18n();

const NEW_FOLDER = "__new__";
const ROOT_FOLDER = "";

const destination = ref<string>(ROOT_FOLDER);
const newFolder = ref("");
const files = ref<File[]>([]);
const formRef = ref<InstanceType<typeof RForm> | null>(null);

type Destination = { value: string; title: string; icon: string };

const destinations = computed<Destination[]>(() => [
  {
    value: NEW_FOLDER,
    title: t("rom.upload-new-folder"),
    icon: "mdi-plus",
  },
  ...props.folders.map((f) => ({
    value: f.value,
    title: f.label,
    icon: f.icon,
  })),
]);
const destinationIcon = computed(
  () => destinations.value.find((d) => d.value === destination.value)?.icon,
);
const isNewFolder = (item: Destination) => item.value === NEW_FOLDER;

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    destination.value = ROOT_FOLDER;
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
          :prepend-inner-icon="destinationIcon"
          :divider-after="isNewFolder"
          hide-details
        >
          <template #item="{ props: itemProps, item, selected }">
            <li v-bind="itemProps">
              <RIcon :icon="item.raw.icon" size="16" />
              <span class="r-select__item-title">{{ item.title }}</span>
              <RIcon
                v-if="selected"
                icon="mdi-check"
                class="r-select__item-check"
                size="x-small"
              />
            </li>
          </template>
        </RSelect>
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
