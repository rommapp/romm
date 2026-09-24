<script setup lang="ts">
// MemoryCardDialog: a memory card's name and visibility. Creating one from
// the picker, creating one from the manager and editing one there are the
// same fields, the same validation and the same footer, so they are one
// dialog with a different title and confirm label.
import { RBtn, RDialog, RForm, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import VisibilitySwitch from "@/v2/components/shared/VisibilitySwitch.vue";
import { required } from "@/v2/utils/validation";

export interface MemoryCardFields {
  name: string;
  isPublic: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    confirmLabel: string;
    /** Prefilled when editing, empty when creating. */
    initialName?: string;
    initialPublic?: boolean;
    icon?: string;
    confirmIcon?: string;
    busy?: boolean;
  }>(),
  {
    initialName: "",
    initialPublic: false,
    icon: "mdi-sd",
    confirmIcon: undefined,
    busy: false,
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", fields: MemoryCardFields): void;
}>();

const { t } = useI18n();

const name = ref(props.initialName);
const isPublic = ref(props.initialPublic);
const valid = ref(true);
const rules = [required(t("common.required"))];
const canSubmit = computed(
  () =>
    !!name.value.trim() &&
    (name.value.trim() !== props.initialName ||
      isPublic.value !== props.initialPublic) &&
    !props.busy,
);

// Reopening is what resets the fields, so a cancelled edit does not carry
// into the next one.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    name.value = props.initialName;
    isPublic.value = props.initialPublic;
  },
  { immediate: true },
);

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  if (!canSubmit.value) return;
  emit("submit", { name: name.value.trim(), isPublic: isPublic.value });
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    :icon="icon"
    :width="420"
    cancelable
    :cancel-disabled="busy"
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
        <div class="r-mc-dialog__fields">
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
          <VisibilitySwitch v-model="isPublic" :disabled="busy" />
        </div>
      </RForm>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        :prepend-icon="confirmIcon"
        :disabled="!canSubmit"
        :loading="busy"
        @click="submit"
      >
        {{ confirmLabel }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-mc-dialog__fields {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}
</style>
