<script setup lang="ts">
// UploadAssetDialog: pick the slot for saves, or the core states were made
// with, then the files to send. The Save data tab owns the upload, and
// closes the dialog first.
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
import type { SaveSchema } from "@/__generated__";
import { SAVE_SLOT_MAX_LENGTH } from "@/services/api/save";
import { formatBytes } from "@/utils";
import {
  chosenSlot,
  isSlotChoice,
  slotChoiceKey,
  slotChoices,
  type SlotChoice,
} from "@/v2/utils/saveSlots";
import { required } from "@/v2/utils/validation";

export type UploadAssetType = "save" | "state";

// A manual upload may also stay out of every slot, as an archive.
type UploadSlot = SlotChoice | { kind: "none" };
const NO_SLOT: UploadSlot = { kind: "none" };

const props = defineProps<{
  modelValue: boolean;
  type: UploadAssetType;
  /** Own saves, whose slots the picker offers. */
  saves: Pick<SaveSchema, "slot">[];
  /** Cores the states may have been made with. */
  cores: string[];
  /** Files dropped on the tab, already picked when the dialog opens. */
  initialFiles: File[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [
    payload: { files: File[]; slot: string | null; emulator: string | null },
  ];
}>();

const { t } = useI18n();

const slot = ref<UploadSlot>(NO_SLOT);
const newSlotName = ref("");
const core = ref("");
const files = ref<File[]>([]);
const formRef = ref<InstanceType<typeof RForm> | null>(null);
const filledDz = ref<InstanceType<typeof RDropzone> | null>(null);

const slotItems = computed<UploadSlot[]>(() => [
  NO_SLOT,
  ...slotChoices(props.saves),
]);
const slotTitle = (choice: UploadSlot) => {
  if (choice.kind === "none") return t("play.slot-none");
  return choice.kind === "new" ? t("play.new-slot") : choice.slot;
};
const slotKey = (choice: UploadSlot) =>
  choice.kind === "none" ? "none" : slotChoiceKey(choice);
function onSlot(value: unknown) {
  if (isSlotChoice(value)) slot.value = value;
  else if (value === NO_SLOT) slot.value = NO_SLOT;
}

const coreItems = computed(() => [
  { value: "", title: t("play.any-core") },
  ...props.cores.map((value) => ({ value, title: value })),
]);

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    slot.value = NO_SLOT;
    newSlotName.value = "";
    core.value = "";
    files.value = [...props.initialFiles];
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
  const picked = slot.value;
  emit("submit", {
    files: files.value,
    slot:
      props.type === "save" && picked.kind !== "none"
        ? chosenSlot(picked, newSlotName.value)
        : null,
    emulator: props.type === "state" ? core.value || null : null,
  });
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-cloud-upload-outline"
    width="520"
    @update:model-value="emit('update:modelValue', $event)"
    @close="close"
  >
    <template #header>
      <span>{{
        type === "save" ? t("rom.upload-saves") : t("rom.upload-states")
      }}</span>
    </template>
    <template #content>
      <RForm ref="formRef" class="r-v2-upload-asset">
        <RSelect
          v-if="type === 'save'"
          :model-value="slot"
          :items="slotItems"
          :item-title="slotTitle"
          :item-value="slotKey"
          return-object
          :label="t('play.slot')"
          :hint="t('rom.upload-slot-hint')"
          @update:model-value="onSlot"
        />
        <RTextField
          v-if="type === 'save' && slot.kind === 'new'"
          v-model="newSlotName"
          :label="t('play.slot-name')"
          :rules="[required()]"
          :maxlength="SAVE_SLOT_MAX_LENGTH"
          autocomplete="off"
        />
        <RSelect
          v-if="type === 'state'"
          v-model="core"
          :items="coreItems"
          :label="t('common.core')"
          :hint="t('rom.upload-core-hint')"
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
          <div class="r-v2-upload-asset__filled">
            <header class="r-v2-upload-asset__head">
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
            <ul class="r-v2-upload-asset__list">
              <li
                v-for="f in files"
                :key="f.name"
                class="r-v2-upload-asset__row"
              >
                <RIcon icon="mdi-file-outline" size="14" />
                <span class="r-v2-upload-asset__name">{{ f.name }}</span>
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
.r-v2-upload-asset {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-upload-asset__filled {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.r-v2-upload-asset__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
}

.r-v2-upload-asset__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.r-v2-upload-asset__row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.r-v2-upload-asset__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
}
</style>
