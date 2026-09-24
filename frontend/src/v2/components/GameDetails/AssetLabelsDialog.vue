<script setup lang="ts">
// AssetLabelsDialog: names the runs behind a save or state ("100% run",
// "Seed: 000X43LKR3"). Submitting no labels clears them.
import { RBtn, RComboboxField, RDialog, RForm } from "@v2/lib";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    /** Prefilled with the asset's current labels. */
    initialLabels?: string[];
    suggestions?: string[];
    busy?: boolean;
    /** Defaults to the field's own name; a bulk edit says "Add labels". */
    title?: string;
  }>(),
  {
    initialLabels: () => [],
    suggestions: () => [],
    busy: false,
    title: undefined,
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", labels: string[]): void;
}>();

const { t } = useI18n();

const labels = ref<string[]>([...props.initialLabels]);

// Reopening is what resets the field, so a cancelled edit does not carry into
// the next one.
watch(
  () => props.modelValue,
  (open) => {
    if (open) labels.value = [...props.initialLabels];
  },
);

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  if (props.busy) return;
  emit("submit", [...labels.value]);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-label-outline"
    :width="460"
    cancelable
    :cancel-disabled="busy"
    @update:model-value="
      (v) => {
        if (!v) close();
      }
    "
  >
    <template #header>
      <span>{{ title ?? t("rom.asset-labels") }}</span>
    </template>

    <template #content>
      <!-- The combobox owns Enter (it commits a label), so the form must not
           also treat it as submit and close on the first one. -->
      <RForm disable-enter-submit>
        <RComboboxField
          v-model="labels"
          :items="suggestions"
          :label="t('rom.asset-labels')"
          :placeholder="t('rom.asset-labels-placeholder')"
          :hint="t('rom.asset-labels-hint')"
          prefix-label="stacked"
          clearable
        />
      </RForm>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-check"
        :loading="busy"
        :disabled="busy"
        @click="submit"
      >
        {{ t("common.save") }}
      </RBtn>
    </template>
  </RDialog>
</template>
