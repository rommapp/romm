<script setup lang="ts">
// AssetCard (v2) — feature composite for the save/state pickers shown
// before launching EmulatorJS. Renders a 16:9 screenshot (states),
// filename, emulator + size chips, and a relative "updated" line.
//
// Lives in `components/Player/` because it knows about SaveSchema /
// StateSchema — domain coupling means it can't be a /lib primitive.
// Built from R primitives + shared utils; no Vuetify.
import { RImg, RTag } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";
import { getEmptyCoverImage } from "@/v2/utils/covers";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";

const props = defineProps<{
  asset: SaveSchema | StateSchema;
  type: AssetType;
}>();

defineEmits<{
  (e: "click", event: MouseEvent): void;
}>();

const { t, locale } = useI18n();

// States carry a screenshot; saves don't. Fall back to a placeholder
// keyed by the file name so identical filenames render the same colour
// — visual cue across the grid that two assets share a base name.
const screenshotSrc = computed(() => {
  if (!("screenshot" in props.asset)) return null;
  return (
    props.asset.screenshot?.download_path ??
    getEmptyCoverImage(props.asset.file_name, 16 / 9)
  );
});

const updatedText = computed(() =>
  formatTimestamp(props.asset.updated_at, locale.value),
);

const relativeText = computed(() => formatRelativeDate(props.asset.updated_at));
</script>

<template>
  <article
    class="r-v2-asset-card"
    role="button"
    tabindex="0"
    :data-asset-type="type"
    @click="(e) => $emit('click', e)"
    @keydown.enter.prevent="(e) => $emit('click', e as unknown as MouseEvent)"
    @keydown.space.prevent="(e) => $emit('click', e as unknown as MouseEvent)"
  >
    <RImg
      v-if="screenshotSrc"
      :src="screenshotSrc"
      :alt="asset.file_name"
      aspect-ratio="16 / 9"
      cover
      class="r-v2-asset-card__screenshot"
    />

    <div class="r-v2-asset-card__body">
      <div class="r-v2-asset-card__name" :title="asset.file_name">
        {{ asset.file_name }}
      </div>

      <div class="r-v2-asset-card__chips">
        <RTag
          v-if="asset.emulator"
          tone="warning"
          size="x-small"
          :text="asset.emulator"
        />
        <RTag size="x-small" :text="formatBytes(asset.file_size_bytes)" />
      </div>

      <div class="r-v2-asset-card__meta">
        <span>{{ t("rom.updated") }}: {{ updatedText }}</span>
        <span class="r-v2-asset-card__relative">({{ relativeText }})</span>
      </div>
    </div>
  </article>
</template>

<style scoped>
.r-v2-asset-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  cursor: pointer;
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
  user-select: none;
}
.r-v2-asset-card:hover {
  border-color: var(--r-color-border-strong);
  background: var(--r-color-surface);
  transform: translateY(-1px);
}
.r-v2-asset-card:active {
  transform: translateY(0);
}

.r-v2-asset-card__screenshot {
  border-radius: var(--r-radius-sm);
  overflow: hidden;
}

.r-v2-asset-card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 2px 2px 0;
}

.r-v2-asset-card__name {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-brand-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-asset-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.r-v2-asset-card__meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-size: 11px;
  color: var(--r-color-fg-secondary);
}
.r-v2-asset-card__relative {
  color: var(--r-color-fg-muted);
}
</style>
