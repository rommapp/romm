<script setup lang="ts">
import { RBtn } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ pinned: boolean }>();
const emit = defineEmits<{ toggle: [] }>();

const { t } = useI18n();

const label = computed(() =>
  props.pinned ? t("rom.unpin-from-overview") : t("rom.pin-to-overview"),
);
</script>

<template>
  <RBtn
    :icon="pinned ? 'mdi-pin' : 'mdi-pin-outline'"
    size="small"
    variant="flat"
    :color="pinned ? 'primary' : undefined"
    :class="{ 'r-v2-media-pin--idle': !pinned }"
    :aria-pressed="pinned"
    :aria-label="label"
    :tooltip="label"
    @click="emit('toggle')"
  />
</template>

<style scoped>
/* Sits on artwork, so it needs the fixed overlay scrim to stay legible. */
.r-btn.r-v2-media-pin--idle {
  background: var(--r-color-overlay-scrim-strong);
  color: var(--r-color-overlay-fg);
}
</style>
