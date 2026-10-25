<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RBtn } from "@/lib";
import type { MetadataLockField } from "@/services/api/rom";

defineOptions({ inheritAttrs: false });

interface Props {
  field: MetadataLockField;
  label: string;
  locked: boolean;
  disabled: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  toggle: [field: MetadataLockField];
}>();

const { t } = useI18n();
const actionLabel = computed(() =>
  t(props.locked ? "rom.unlock-metadata" : "rom.lock-metadata"),
);
</script>

<template>
  <RBtn
    v-bind="$attrs"
    :icon="locked ? 'mdi-lock' : 'mdi-lock-open-outline'"
    variant="text"
    density="compact"
    :disabled="disabled"
    :tooltip="`${actionLabel}: ${label}`"
    :aria-label="`${actionLabel}: ${label}`"
    @click="emit('toggle', field)"
  />
</template>
