<script setup lang="ts">
// ViewerZoomControls: zoom out / level / zoom in / fit toggle, shared by the
// PDF and image doc viewers' toolbars. State lives in `useViewerZoom`.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { FitMode } from "@/composables/useViewerZoom";
import { RBtn } from "@/lib";

const props = defineProps<{
  zoom: number;
  fit: FitMode;
  canZoomIn: boolean;
  canZoomOut: boolean;
}>();

const emit = defineEmits<{
  zoomIn: [];
  zoomOut: [];
  toggleFit: [];
}>();

const { t } = useI18n();

// The button offers the other mode, so it is labelled with what it switches to.
const fitLabel = computed(() =>
  props.fit === "page" ? t("rom.fit-width") : t("rom.fit-page"),
);
const fitIcon = computed(() =>
  props.fit === "page"
    ? "mdi-arrow-expand-horizontal"
    : "mdi-fit-to-page-outline",
);
</script>

<template>
  <RBtn
    icon="mdi-magnify-minus-outline"
    variant="text"
    size="small"
    :tooltip="t('common.zoom-out')"
    :aria-label="t('common.zoom-out')"
    :disabled="!canZoomOut"
    @click="emit('zoomOut')"
  />
  <span class="r-zoom__level" aria-live="polite">
    {{ Math.round(zoom * 100) }}%
  </span>
  <RBtn
    icon="mdi-magnify-plus-outline"
    variant="text"
    size="small"
    :tooltip="t('common.zoom-in')"
    :aria-label="t('common.zoom-in')"
    :disabled="!canZoomIn"
    @click="emit('zoomIn')"
  />
  <RBtn
    :icon="fitIcon"
    variant="text"
    size="small"
    :tooltip="fitLabel"
    :aria-label="fitLabel"
    @click="emit('toggleFit')"
  />
</template>

<style scoped>
.r-zoom__level {
  min-width: 40px;
  text-align: center;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}
</style>
