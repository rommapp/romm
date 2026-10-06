<script setup lang="ts">
import { RBtn, RDialog, RForm, RSelect, RTextField } from "@v2/lib";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { CHANNEL_LABEL_MAX_LENGTH } from "@/services/api/snapshot";
import { notBlank } from "@/v2/utils/validation";

export interface StartOption {
  /** A save to copy in, or null to start the channel empty. */
  saveId: number | null;
  title: string;
}

export interface ChannelLabelSubmit {
  label: string;
  startFrom: number | null;
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    confirmText: string;
    initialLabel?: string;
    /** Offered when a new channel can start from an existing save. */
    startOptions?: StartOption[];
    busy?: boolean;
  }>(),
  { initialLabel: "", startOptions: () => [], busy: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", value: ChannelLabelSubmit): void;
}>();

const { t } = useI18n();

const formRef = ref<InstanceType<typeof RForm> | null>(null);
const label = ref("");
const startFrom = ref<number | null>(null);

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    label.value = props.initialLabel;
    startFrom.value = props.startOptions[0]?.saveId ?? null;
  },
);

function close(): void {
  emit("update:modelValue", false);
}

async function submit(): Promise<void> {
  if (props.busy) return;
  const result = await formRef.value?.validate();
  if (result && !result.valid) return;
  emit("submit", { label: label.value.trim(), startFrom: startFrom.value });
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-layers-outline"
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
      <span>{{ title }}</span>
    </template>

    <template #content>
      <RForm ref="formRef" class="r-channel-label-dialog" @submit="submit">
        <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the first field on dialog open is intentional modal UX -->
        <RTextField
          v-model="label"
          :label="t('channels.label')"
          prefix-label="stacked"
          :maxlength="CHANNEL_LABEL_MAX_LENGTH"
          :rules="[notBlank()]"
          autofocus
        />
        <!-- eslint-enable vuejs-accessibility/no-autofocus -->
        <RSelect
          v-if="startOptions.length > 1"
          v-model="startFrom"
          :items="startOptions"
          item-title="title"
          item-value="saveId"
          :label="t('channels.start-from')"
          prefix-label="stacked"
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
        {{ confirmText }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-channel-label-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
</style>
