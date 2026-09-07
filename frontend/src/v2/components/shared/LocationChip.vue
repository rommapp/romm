<script setup lang="ts">
// LocationChip — click-to-copy chip surfacing a ROM's on-disk location, built
// on HashChip's pattern (a keyboard-accessible <button> shell around RTag) so
// it reads as a sibling of the hash pills beside it. A path ellipsis-truncates
// on overflow rather than being mid-abbreviated; the full path is what copies.
import { RTag } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { useClipboard } from "@/v2/composables/useClipboard";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ path: string }>();

const { t } = useI18n();
const clipboard = useClipboard();

async function copy() {
  await clipboard.copy(props.path, {
    successMessage: t("rom.location-copied"),
  });
}
</script>

<template>
  <button
    type="button"
    class="r-v2-location-chip"
    :title="`${t('rom.location')}: ${path}`"
    :aria-label="`${t('rom.location')}: ${path}`"
    @click="copy"
  >
    <RTag
      prepend-icon="mdi-map-marker-outline"
      :text="path"
      append-icon="mdi-content-copy"
      size="small"
      mono
    />
  </button>
</template>

<style scoped>
/* The button is just the interactive shell, RTag owns the visuals.
   Stripping native chrome so hover / active styles lean on the inner tag. */
.r-v2-location-chip {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  margin: 0;
  font: inherit;
  cursor: pointer;
  display: inline-flex;
  min-width: 0;
  max-width: 100%;
  border-radius: var(--r-radius-chip);
  transition: transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-location-chip:hover :deep(.r-tag) {
  border-color: var(--r-color-fg-muted);
  background: var(--r-color-surface-hover);
}
.r-v2-location-chip:active {
  transform: scale(0.98);
}
/* Ellipsis-truncate the path text rather than mid-abbreviate it. */
.r-v2-location-chip :deep(.r-tag) {
  max-width: 100%;
}
.r-v2-location-chip :deep(.r-tag__text) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
