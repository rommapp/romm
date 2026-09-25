<script setup lang="ts">
// AppriseFieldInput: one field of an Apprise service, in the control its type
// calls for.
import { RCheckbox, RComboboxField, RSelect, RTextField } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { AppriseFieldSchema } from "@/__generated__";
import {
  type AppriseFieldValue,
  NOTIFICATION_CHANNEL_URL_MAX_LENGTH,
  TRANSLATED_APPRISE_FIELDS,
} from "@/v2/utils/notificationChannels";
import { notBlank } from "@/v2/utils/validation";

const props = defineProps<{
  field: AppriseFieldSchema;
  // A secret the channel already has, which stays when left empty.
  stored: boolean;
  // A required list left empty, which the combobox can't flag by itself.
  missing: boolean;
}>();
const value = defineModel<AppriseFieldValue>({ required: true });
const removed = defineModel<boolean>("removed", { default: false });

const { t } = useI18n();

const label = computed(() =>
  TRANSLATED_APPRISE_FIELDS.has(props.field.key)
    ? t(`notifications.channel-field-${props.field.key}`)
    : props.field.label,
);
const required = computed(() => props.field.required && !props.stored);
const hint = computed(() =>
  props.stored ? t("notifications.channel-secret-keep") : undefined,
);
const isNumber = computed(
  () => props.field.type === "int" || props.field.type === "float",
);

function inRange(text: string): true | string {
  const { min, max, type } = props.field;
  const n = Number(text);
  const fits =
    text === "" ||
    (!Number.isNaN(n) &&
      (type === "float" || Number.isInteger(n)) &&
      (min === null || n >= min) &&
      (max === null || n <= max));
  return (
    fits ||
    t("notifications.channel-field-number", {
      min: min ?? "−∞",
      max: max ?? "∞",
    })
  );
}

const rules = computed(() => [
  ...(required.value ? [notBlank()] : []),
  ...(isNumber.value ? [inRange] : []),
]);
</script>

<template>
  <div class="r-v2-apprise-field">
    <RCheckbox
      v-if="field.type === 'bool'"
      :model-value="value === true"
      :label="label"
      @update:model-value="value = $event === true"
    />
    <RSelect
      v-else-if="field.type === 'choice'"
      :model-value="value"
      :items="field.values ?? []"
      :label="label"
      prefix-label="stacked"
      hide-details
      @update:model-value="value = String($event)"
    />
    <RComboboxField
      v-else-if="field.type === 'list'"
      :model-value="Array.isArray(value) ? value : []"
      :label="label"
      :hint="hint ?? t('notifications.channel-field-list-hint')"
      :error-messages="missing ? t('common.required') : undefined"
      :disabled="removed"
      prefix-label="stacked"
      no-suggestions
      @update:model-value="value = $event"
    />
    <RTextField
      v-else
      :model-value="String(value)"
      :label="label"
      :type="field.private ? 'password' : isNumber ? 'number' : 'text'"
      :rules="rules"
      :required="required"
      :hint="hint"
      :disabled="removed"
      :maxlength="NOTIFICATION_CHANNEL_URL_MAX_LENGTH"
      :autocomplete="field.private ? 'new-password' : 'off'"
      prefix-label="stacked"
      @update:model-value="value = String($event ?? '')"
    />
    <RCheckbox
      v-if="stored && !field.required"
      v-model="removed"
      :label="t('notifications.channel-secret-remove')"
    />
  </div>
</template>

<style scoped>
.r-v2-apprise-field {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
  min-width: 0;
}
</style>
