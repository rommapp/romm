<script setup lang="ts">
// MemoryCardNameDialog: the shared "name a memory card" prompt. Creating one
// from the picker, creating one from the manager and renaming one there are
// the same field, the same validation and the same footer, so they are one
// dialog with a different title and confirm label.
import { RBtn, RDialog, RForm, RTextField } from "@v2/lib";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { required } from "@/v2/utils/validation";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    confirmLabel: string;
    /** Prefilled when renaming, empty when creating. */
    initialName?: string;
    icon?: string;
    confirmIcon?: string;
    busy?: boolean;
  }>(),
  { initialName: "", icon: "mdi-sd", confirmIcon: undefined, busy: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", name: string): void;
}>();

const { t } = useI18n();

const name = ref(props.initialName);
const valid = ref(true);
const rules = [required(t("common.required"))];

// Reopening is what resets the field, so a cancelled rename does not carry its
// edit into the next one.
watch(
  () => props.modelValue,
  (open) => {
    if (open) name.value = props.initialName;
  },
  { immediate: true },
);

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  const trimmed = name.value.trim();
  if (!trimmed || props.busy) return;
  emit("submit", trimmed);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    :icon="icon"
    :width="420"
    @update:model-value="
      (v) => {
        if (!v) close();
      }
    "
    @close="close"
  >
    <template #header>
      <span>{{ title }}</span>
    </template>

    <template #content>
      <RForm v-model="valid" @submit="submit">
        <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the first field on dialog open is intentional modal UX -->
        <RTextField
          v-model="name"
          :placeholder="t('common.name')"
          prefix-label="stacked"
          :rules="rules"
          required
          autofocus
        >
          <template #prefix-label>
            {{ t("common.name") }}
          </template>
        </RTextField>
        <!-- eslint-enable vuejs-accessibility/no-autofocus -->
      </RForm>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="busy" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        :prepend-icon="confirmIcon"
        :disabled="!name.trim() || busy"
        :loading="busy"
        @click="submit"
      >
        {{ confirmLabel }}
      </RBtn>
    </template>
  </RDialog>
</template>
