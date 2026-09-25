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
  appriseFieldLabel,
} from "@/v2/utils/notificationChannels";
import { notBlank } from "@/v2/utils/validation";

const props = defineProps<{
  field: AppriseFieldSchema;
  // A secret the channel already has, which stays when left empty.
  stored: boolean;
  // Just filled in from a pasted URL.
  highlight: boolean;
}>();
const value = defineModel<AppriseFieldValue>({ required: true });
const removed = defineModel<boolean>("removed", { default: false });

const { t } = useI18n();

const label = computed(() => appriseFieldLabel(props.field, t));
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
const listRules = computed(() =>
  required.value
    ? [(items: string[]) => items.length > 0 || t("common.required")]
    : [],
);
</script>

<template>
  <div
    class="r-v2-apprise-field"
    :class="{ 'r-v2-apprise-field--filled': highlight }"
  >
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
      :rules="listRules"
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
  border-radius: var(--r-radius-md);
}

.r-v2-apprise-field--filled {
  animation: r-v2-apprise-field-filled 1.6s var(--r-motion-ease-out);
}

@keyframes r-v2-apprise-field-filled {
  from {
    box-shadow: 0 0 0 3px
      color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
  }
  to {
    box-shadow: 0 0 0 3px transparent;
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-v2-apprise-field--filled {
    animation: none;
  }
}
</style>
