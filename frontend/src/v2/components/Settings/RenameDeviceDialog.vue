<script setup lang="ts">
import { RBtn, RDialog, RForm, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { notBlank } from "@/v2/utils/validation";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    name: string;
    busy?: boolean;
  }>(),
  { busy: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", name: string): void;
}>();

const { t } = useI18n();

const draft = ref(props.name);
const trimmed = computed(() => draft.value.trim());
const rules = [notBlank()];
const canSubmit = computed(
  () => !!trimmed.value && trimmed.value !== props.name && !props.busy,
);

// Reopening resets the field, so a cancelled rename does not carry over.
watch(
  () => props.modelValue,
  (open) => {
    if (open) draft.value = props.name;
  },
  { immediate: true },
);

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  if (!canSubmit.value) return;
  emit("submit", trimmed.value);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-pencil-outline"
    :width="420"
    cancelable
    :cancel-disabled="busy"
    @update:model-value="
      (v) => {
        if (!v) close();
      }
    "
  >
    <template #header>
      <span>{{ t("settings.device-rename") }}</span>
    </template>

    <template #content>
      <RForm @submit="submit">
        <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the only field on dialog open is intentional modal UX -->
        <RTextField
          v-model="draft"
          :label="t('common.name')"
          prefix-label="stacked"
          :rules="rules"
          required
          autofocus
        />
        <!-- eslint-enable vuejs-accessibility/no-autofocus -->
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
