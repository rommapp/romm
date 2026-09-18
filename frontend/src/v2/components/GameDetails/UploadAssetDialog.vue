<script setup lang="ts">
// UploadAssetDialog: the slot for saves, or the core for states, plus the
// files to send. The Save data tab owns the upload.
import { RBtn, RDialog, RForm, RIcon, RSelect, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema } from "@/__generated__";
import { AUTOSAVE_SLOT, SAVE_SLOT_MAX_LENGTH } from "@/services/api/save";
import PendingFilesDropzone from "@/v2/components/shared/PendingFilesDropzone.vue";
import type { AssetType } from "@/v2/utils/assets";
import {
  chosenSlot,
  existingSlot,
  isNewSlotChoice,
  isSlotChoice,
  slotChoiceKey,
  slotChoiceTitle,
  slotChoices,
  type SlotChoice,
} from "@/v2/utils/saveSlots";
import { notBlank } from "@/v2/utils/validation";

export interface UploadAssetPayload {
  type: AssetType;
  files: File[];
  slot: string | null;
  emulator: string | null;
}

// A manual upload may also stay out of every slot, as an archive.
type UploadSlot = SlotChoice | { kind: "none" };
const NO_SLOT: UploadSlot = { kind: "none" };

const props = defineProps<{
  modelValue: boolean;
  type: AssetType;
  /** Own saves, whose slots the picker offers. */
  saves: Pick<SaveSchema, "slot">[];
  /** Cores the states may have been made with. */
  cores: string[];
  /** Files dropped on the tab, already picked when the dialog opens. */
  initialFiles: File[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
  submit: [payload: UploadAssetPayload];
}>();

const { t } = useI18n();

const slot = ref<UploadSlot>(existingSlot(AUTOSAVE_SLOT));
const newSlotName = ref("");
const core = ref("");
const files = ref<File[]>([]);
const formRef = ref<InstanceType<typeof RForm> | null>(null);

const slotItems = computed<UploadSlot[]>(() => [
  ...slotChoices(props.saves),
  NO_SLOT,
]);
const slotTitle = (choice: UploadSlot) =>
  choice.kind === "none" ? t("play.slot-none") : slotChoiceTitle(choice);
const slotKey = (choice: UploadSlot) =>
  choice.kind === "none" ? "none" : slotChoiceKey(choice);
function isUploadSlot(value: unknown): value is UploadSlot {
  return (
    isSlotChoice(value) ||
    (typeof value === "object" &&
      value !== null &&
      "kind" in value &&
      value.kind === "none")
  );
}
function onSlot(value: unknown) {
  if (isUploadSlot(value)) slot.value = value;
}

const coreItems = computed(() => [
  { value: "", title: t("play.any-core") },
  ...props.cores.map((value) => ({ value, title: value })),
]);

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    slot.value = existingSlot(AUTOSAVE_SLOT);
    newSlotName.value = "";
    core.value = "";
    files.value = [];
    addFiles(props.initialFiles);
  },
  { immediate: true },
);

function addFiles(picked: File[]) {
  const seen = new Set(files.value.map((f) => f.name));
  files.value = [...files.value, ...picked.filter((f) => !seen.has(f.name))];
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
    type: props.type,
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
  >
    <template #header>
      <span>{{
        type === "save" ? t("rom.upload-saves") : t("rom.upload-states")
      }}</span>
    </template>
    <template #content>
      <RForm ref="formRef" class="r-v2-upload-asset" @submit="submit">
        <RSelect
          v-if="type === 'save'"
          :model-value="slot"
          :items="slotItems"
          :item-title="slotTitle"
          :item-value="slotKey"
          return-object
          :divider-after="isNewSlotChoice"
          prefix-label="inline"
          :hint="t('rom.upload-slot-hint')"
          @update:model-value="onSlot"
        >
          <template #prefix-label>
            <RIcon icon="mdi-content-save-all-outline" size="14" />
            {{ t("play.slot") }}
          </template>
        </RSelect>
        <RTextField
          v-if="type === 'save' && slot.kind === 'new'"
          v-model="newSlotName"
          :label="t('play.slot-name')"
          :rules="[notBlank()]"
          :maxlength="SAVE_SLOT_MAX_LENGTH"
          autocomplete="off"
        />
        <RSelect
          v-if="type === 'state'"
          v-model="core"
          :items="coreItems"
          prefix-label="inline"
          :hint="t('rom.upload-core-hint')"
        >
          <template #prefix-label>
            <RIcon icon="mdi-chip" size="14" />
            {{ t("common.core") }}
          </template>
        </RSelect>
        <PendingFilesDropzone
          v-model="files"
          :input-label="t('common.upload')"
        />
      </RForm>
    </template>
    <template #footer>
      <RBtn variant="outlined" @click="close">
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
</style>
