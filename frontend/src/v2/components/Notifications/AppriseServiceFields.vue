<script setup lang="ts">
// AppriseServiceFields: the fields an Apprise service takes, as the backend
// lists them, with its options folded under "Advanced options".
import { RBtn, RCollapsible } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { AppriseFieldSchema, AppriseServiceSchema } from "@/__generated__";
import AppriseFieldInput from "@/v2/components/Notifications/AppriseFieldInput.vue";
import type { AppriseFieldValue } from "@/v2/utils/notificationChannels";

const props = defineProps<{
  service: AppriseServiceSchema;
  // The secrets the channel already has.
  stored: string[];
  // The fields a pasted URL just filled in.
  highlighted: string[];
}>();
const values = defineModel<Record<string, AppriseFieldValue>>({
  required: true,
});
// The stored secrets to drop on save.
const removed = defineModel<string[]>("removed", { default: () => [] });

const { t } = useI18n();

// A service set up from its own URL shows only what that URL lacks.
const basic = computed(() =>
  props.service.fields.filter(
    (f) => !f.advanced && !props.service.url_fields.includes(f.key),
  ),
);
const advanced = computed(() => props.service.fields.filter((f) => f.advanced));
const showAdvanced = ref(false);

function set(key: string, value: AppriseFieldValue) {
  values.value = { ...values.value, [key]: value };
}

function inputProps(field: AppriseFieldSchema) {
  return {
    field,
    modelValue: values.value[field.key],
    stored: props.stored.includes(field.key),
    highlight: props.highlighted.includes(field.key),
    removed: removed.value.includes(field.key),
  };
}

function setRemoved(key: string, drop: boolean) {
  removed.value = drop
    ? [...removed.value, key]
    : removed.value.filter((k) => k !== key);
}
</script>

<template>
  <div v-if="basic.length > 0" class="r-v2-apprise-fields">
    <AppriseFieldInput
      v-for="field in basic"
      :key="field.key"
      v-bind="inputProps(field)"
      @update:model-value="set(field.key, $event)"
      @update:removed="setRemoved(field.key, $event)"
    />
  </div>
  <template v-if="advanced.length > 0">
    <RBtn
      class="r-v2-apprise-fields__toggle"
      variant="text"
      size="small"
      :prepend-icon="showAdvanced ? 'mdi-chevron-down' : 'mdi-chevron-right'"
      :aria-expanded="showAdvanced"
      @click="showAdvanced = !showAdvanced"
    >
      {{ t("notifications.channel-advanced") }}
    </RBtn>
    <RCollapsible v-model="showAdvanced">
      <div class="r-v2-apprise-fields r-v2-apprise-fields--inset">
        <AppriseFieldInput
          v-for="field in advanced"
          :key="field.key"
          v-bind="inputProps(field)"
          @update:model-value="set(field.key, $event)"
          @update:removed="setRemoved(field.key, $event)"
        />
      </div>
    </RCollapsible>
  </template>
</template>

<style scoped>
.r-v2-apprise-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: var(--r-space-3);
}

.r-v2-apprise-fields__toggle {
  align-self: flex-start;
}

.r-v2-apprise-fields--inset {
  padding: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-apprise-fields {
  grid-template-columns: minmax(0, 1fr);
}
</style>
