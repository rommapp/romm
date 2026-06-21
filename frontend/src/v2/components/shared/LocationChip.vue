<script setup lang="ts">
// LocationChip — click-to-copy chip surfacing a ROM's on-disk location
// (the directory it lives in plus its name). Mirrors HashChip's pattern —
// a keyboard-accessible <button> shell wrapping the shared RTag primitive —
// so it reads as a sibling of the hash pills it sits next to. Unlike a hash,
// a path isn't mid-abbreviated: it ellipsis-truncates on overflow while the
// full untruncated path is what gets copied.
import { RTag } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ path: string }>();

const { t } = useI18n();
const snackbar = useSnackbar();

async function copy() {
  try {
    await navigator.clipboard.writeText(props.path);
    snackbar.success(t("rom.location-copied"), { icon: "mdi-check-bold" });
  } catch {
    snackbar.error(t("common.clipboard-unavailable"), {
      icon: "mdi-close-circle",
    });
  }
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
/* The button is just the interactive shell — RTag owns the visuals.
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
