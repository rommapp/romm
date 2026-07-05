<script setup lang="ts">
// InfoPanel — hero strip at the top of Platform / Collection gallery
// pages (matches the artist mockup's `.plat-info-panel`). Feature
// composite around Stat, chips, and callsite-provided cover art.
//
// Slots: cover, eyebrow, title (defaults to `title` prop), tags, stats,
// providers, actions.
//
// `providers` sits below stats — used by Platform.vue to surface the
// external-metadata chip cluster (IGDB / SS / MobyGames / RA / …)
// inline rather than buried in a drawer.
//
// IMPORTANT — no divider here. The gallery shell owns the divider
// between the hero (header) and the toolbar so all three views
// (Platform / Collection / Search) get the same separator regardless
// of which header they render. The InfoPanel just provides the inner
// content and its own padding for breathing.

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    title?: string;
  }>(),
  {
    title: undefined,
  },
);
</script>

<template>
  <div class="info-panel">
    <div class="info-panel__cover">
      <slot name="cover" />
    </div>
    <div class="info-panel__details">
      <div v-if="$slots.eyebrow" class="info-panel__eyebrow">
        <slot name="eyebrow" />
      </div>
      <h1 class="info-panel__title">
        <slot name="title">{{ title }}</slot>
      </h1>
      <div v-if="$slots.tags" class="info-panel__tags">
        <slot name="tags" />
      </div>
      <div v-if="$slots.stats" class="info-panel__stats">
        <slot name="stats" />
      </div>
      <div v-if="$slots.providers" class="info-panel__providers">
        <slot name="providers" />
      </div>
    </div>
    <div v-if="$slots.actions" class="info-panel__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.info-panel {
  display: flex;
  align-items: flex-start;
  gap: 40px;
  padding: 28px 0;
}

.info-panel__cover {
  flex-shrink: 0;
  align-self: stretch;
  display: flex;
  align-items: center;
  justify-content: center;
}

.info-panel__details {
  flex: 1;
  min-width: 0;
}

.info-panel__eyebrow {
  margin-bottom: 6px;
}

.info-panel__title {
  font-size: var(--r-font-size-3xl);
  font-weight: var(--r-font-weight-extrabold);
  letter-spacing: -0.025em;
  color: var(--r-color-fg);
  line-height: 1.1;
  margin: 0 0 10px 0;
}

.info-panel__tags {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}

.info-panel__stats {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}

.info-panel__providers {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.info-panel__actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

html[data-bp~="xs"] .info-panel {
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 16px 0;
}
/* Drive the vertical rhythm purely from one flex gap on xs — the
   per-child margins (title / tags / providers) compound with the column
   gap otherwise and the stack reads cramped + uneven. Centre the whole
   hero (cover, title, chip clusters) so it reads as a balanced mobile
   header rather than a left-hugging column. */
html[data-bp~="xs"] .info-panel__details {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
  text-align: center;
}
html[data-bp~="xs"] .info-panel__tags,
html[data-bp~="xs"] .info-panel__stats,
html[data-bp~="xs"] .info-panel__providers {
  justify-content: center;
}
html[data-bp~="xs"] .info-panel__title {
  font-size: var(--r-font-size-2xl);
  margin-bottom: 0;
}
html[data-bp~="xs"] .info-panel__tags {
  margin-bottom: 0;
}
html[data-bp~="xs"] .info-panel__providers {
  margin-top: 0;
}
html[data-bp~="xs"] .info-panel__stats {
  gap: 16px;
}
html[data-bp~="xs"] .info-panel__cover {
  align-self: center;
}
</style>
