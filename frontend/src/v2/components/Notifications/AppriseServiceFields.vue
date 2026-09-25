<script setup lang="ts">
// AppriseServiceFields: the fields an Apprise service takes, as the backend
// lists them, with its options folded under "Advanced options".
import { RCollapsible } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { AppriseServiceSchema } from "@/__generated__";
import AppriseFieldInput from "@/v2/components/Notifications/AppriseFieldInput.vue";
import type { AppriseFieldValue } from "@/v2/utils/notificationChannels";

const props = defineProps<{
  service: AppriseServiceSchema;
  editing: boolean;
  // Required lists left empty since the last save attempt.
  missing: string[];
}>();
const values = defineModel<Record<string, AppriseFieldValue>>({
  required: true,
});

const { t } = useI18n();

const basic = computed(() => props.service.fields.filter((f) => !f.advanced));
const advanced = computed(() => props.service.fields.filter((f) => f.advanced));

function set(key: string, value: AppriseFieldValue) {
  values.value = { ...values.value, [key]: value };
}
</script>

<template>
  <div class="r-v2-apprise-fields">
    <AppriseFieldInput
      v-for="field in basic"
      :key="field.key"
      :model-value="values[field.key]"
      :field="field"
      :editing="editing"
      :missing="missing.includes(field.key)"
      @update:model-value="set(field.key, $event)"
    />
  </div>
  <RCollapsible
    v-if="advanced.length > 0"
    :title="t('notifications.channel-advanced')"
    icon="mdi-tune-variant"
  >
    <div class="r-v2-apprise-fields r-v2-apprise-fields--inset">
      <AppriseFieldInput
        v-for="field in advanced"
        :key="field.key"
        :model-value="values[field.key]"
        :field="field"
        :editing="editing"
        :missing="false"
        @update:model-value="set(field.key, $event)"
      />
    </div>
  </RCollapsible>
</template>

<style scoped>
.r-v2-apprise-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: var(--r-space-3);
}

.r-v2-apprise-fields--inset {
  padding: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-apprise-fields {
  grid-template-columns: minmax(0, 1fr);
}
</style>
