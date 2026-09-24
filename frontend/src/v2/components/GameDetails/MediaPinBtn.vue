<script setup lang="ts">
import { RBtn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ pinned: boolean }>();
const emit = defineEmits<{ toggle: [] }>();

const { t } = useI18n();

const label = computed(() =>
  props.pinned ? t("rom.unpin-from-overview") : t("rom.pin-to-overview"),
);
</script>

<template>
  <RBtn
    v-bind="$attrs"
    :icon="pinned ? 'mdi-pin' : 'mdi-pin-outline'"
    size="small"
    variant="flat"
    :color="pinned ? 'primary' : undefined"
    :aria-pressed="pinned"
    :aria-label="label"
    :tooltip="label"
    @click="emit('toggle')"
  />
</template>
