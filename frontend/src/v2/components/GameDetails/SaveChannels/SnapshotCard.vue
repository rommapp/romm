<script setup lang="ts">
import { RChip, RIcon, RImg } from "@v2/lib";

export interface CardBadge {
  label: string;
  color?: string;
  outlined?: boolean;
}

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    title: string;
    subtitle: string;
    thumbnail?: string | undefined;
    badges?: CardBadge[];
    /** The snapshot the channel points at. */
    current?: boolean;
    /** Kept but not current: a branch, or a save without a snapshot. */
    muted?: boolean;
    caption?: string | undefined;
  }>(),
  {
    thumbnail: undefined,
    badges: () => [],
    current: false,
    muted: false,
    caption: undefined,
  },
);

const emit = defineEmits<{ open: [] }>();
</script>

<template>
  <button
    type="button"
    class="r-snapshot-card"
    :class="{
      'r-snapshot-card--current': current,
      'r-snapshot-card--muted': muted,
    }"
    v-bind="$attrs"
    :aria-current="current ? 'true' : undefined"
    @click="emit('open')"
  >
    <RImg
      v-if="thumbnail"
      class="r-snapshot-card__thumb"
      :src="thumbnail"
      cover
      aspect-ratio="4/3"
    />
    <span v-else class="r-snapshot-card__thumb r-snapshot-card__thumb--empty">
      <RIcon icon="mdi-content-save-outline" size="24" />
    </span>
    <span class="r-snapshot-card__body">
      <span class="r-snapshot-card__title">{{ title }}</span>
      <span class="r-snapshot-card__subtitle">{{ subtitle }}</span>
      <span class="r-snapshot-card__badges">
        <span v-if="caption" class="r-snapshot-card__caption">{{
          caption
        }}</span>
        <RChip
          v-for="badge in badges"
          :key="badge.label"
          size="x-small"
          :color="badge.color"
          :variant="badge.outlined ? 'outlined' : 'translucent'"
        >
          {{ badge.label }}
        </RChip>
      </span>
    </span>
  </button>
</template>

<style scoped>
.r-snapshot-card {
  appearance: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  box-shadow: var(--r-elev-1);
}
.r-snapshot-card--current {
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 0 0 1px var(--r-color-brand-primary);
}
.r-snapshot-card--muted {
  border-style: dashed;
  opacity: 0.85;
}
.r-snapshot-card__thumb {
  display: block;
  width: 100%;
  aspect-ratio: 4 / 3;
}
.r-snapshot-card__thumb--empty {
  display: grid;
  place-items: center;
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
}
.r-snapshot-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
  padding: var(--r-space-2) 10px 10px;
}
.r-snapshot-card__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-snapshot-card__subtitle {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
.r-snapshot-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-1);
  align-items: center;
}
.r-snapshot-card__caption {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
</style>
