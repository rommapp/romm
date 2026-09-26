<script setup lang="ts">
// AssetEditDialog: one save's or state's file name, labels and visibility.
// The stem opens selected, so typing over it keeps the extension.
import { RBtn, RComboboxField, RDialog, RForm, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import VisibilitySwitch from "@/v2/components/shared/VisibilitySwitch.vue";
import type { AssetType } from "@/v2/utils/assets";
import { notBlank } from "@/v2/utils/validation";

/** The fields the user changed; the others are left out. */
export interface AssetEdit {
  fileName?: string;
  labels?: string[];
  isPublic?: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    type: AssetType;
    fileName: string;
    labels?: string[];
    isPublic?: boolean;
    suggestions?: string[];
    busy?: boolean;
    /** A name the server refused as taken, flagged while the field holds it. */
    takenName?: string | null;
  }>(),
  {
    labels: () => [],
    isPublic: false,
    suggestions: () => [],
    busy: false,
    takenName: null,
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", edit: AssetEdit): void;
}>();

const { t } = useI18n();

const name = ref(props.fileName);
const labels = ref<string[]>([...props.labels]);
const isPublic = ref(props.isPublic);

const trimmed = computed(() => name.value.trim());
const rules = [notBlank()];
const nameErrors = computed(() =>
  props.takenName !== null && trimmed.value === props.takenName
    ? [t("rom.file-name-taken")]
    : [],
);
const edit = computed(() => {
  const changed: AssetEdit = {};
  if (trimmed.value !== props.fileName) changed.fileName = trimmed.value;
  if (labels.value.join("\n") !== props.labels.join("\n")) {
    changed.labels = [...labels.value];
  }
  if (isPublic.value !== props.isPublic) changed.isPublic = isPublic.value;
  return changed;
});
const canSubmit = computed(
  () =>
    !!trimmed.value &&
    nameErrors.value.length === 0 &&
    Object.keys(edit.value).length > 0 &&
    !props.busy,
);

// Only the focus that opens the dialog selects the stem, so a click back into
// the field leaves the caret where the user put it.
let selectStem = false;

// Reopening is what resets the fields, so a cancelled edit does not carry
// into the next one.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    name.value = props.fileName;
    labels.value = [...props.labels];
    isPublic.value = props.isPublic;
    selectStem = true;
  },
  { immediate: true },
);

function onNameFocus(evt: FocusEvent): void {
  if (!selectStem || !(evt.target instanceof HTMLInputElement)) return;
  selectStem = false;
  const dot = name.value.lastIndexOf(".");
  evt.target.setSelectionRange(0, dot > 0 ? dot : name.value.length);
}

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  if (!canSubmit.value) return;
  emit("submit", edit.value);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-pencil-outline"
    :width="480"
    cancelable
    :cancel-disabled="busy"
    @update:model-value="
      (v) => {
        if (!v) close();
      }
    "
  >
    <template #header>
      <span>
        {{ type === "save" ? t("rom.edit-save") : t("rom.edit-state") }}
      </span>
    </template>

    <template #content>
      <!-- The combobox owns Enter (it commits a label), so the form must not
           also treat it as submit and close on the first one. -->
      <RForm disable-enter-submit>
        <div class="r-asset-edit">
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the first field on dialog open is intentional modal UX -->
          <RTextField
            v-model="name"
            :label="t('rom.filename')"
            prefix-label="stacked"
            :rules="rules"
            :error-messages="nameErrors"
            required
            autofocus
            @focus="onNameFocus"
          />
          <!-- eslint-enable vuejs-accessibility/no-autofocus -->
          <RComboboxField
            v-model="labels"
            :items="suggestions"
            :label="t('rom.asset-labels')"
            :placeholder="t('rom.asset-labels-placeholder')"
            :hint="t('rom.asset-labels-hint')"
            prefix-label="stacked"
            clearable
          />
          <VisibilitySwitch v-model="isPublic" />
        </div>
      </RForm>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-check"
        :loading="busy"
        :disabled="!canSubmit"
        @click="submit"
      >
        {{ t("common.save") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-asset-edit {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}
</style>
