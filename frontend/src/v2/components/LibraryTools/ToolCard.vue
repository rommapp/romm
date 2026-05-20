<script setup lang="ts">
// ToolCard — single tile in the LibraryToolsShell hero card-picker.
// Acts as a router-link with an `active` visual state when the
// current route matches its tool.
//
// Extracted so the three tools (Scan / Upload / Patcher) share one
// markup + style surface instead of repeating the same flex/icon
// layout three times in the shell.
import { RIcon } from "@v2/lib";
import type { RouteLocationRaw } from "vue-router";

defineOptions({ inheritAttrs: false });

interface Props {
  to: RouteLocationRaw;
  icon: string;
  label: string;
  description: string;
  active?: boolean;
  disabled?: boolean;
}

withDefaults(defineProps<Props>(), {
  active: false,
  disabled: false,
});
</script>

<template>
  <component
    :is="disabled ? 'div' : 'router-link'"
    :to="disabled ? undefined : to"
    class="r-v2-tool-card"
    :class="{
      'r-v2-tool-card--active': active,
      'r-v2-tool-card--disabled': disabled,
    }"
    :aria-current="active ? 'page' : undefined"
    :aria-disabled="disabled ? true : undefined"
  >
    <span class="r-v2-tool-card__icon">
      <RIcon :icon="icon" size="28" />
    </span>
    <span class="r-v2-tool-card__body">
      <span class="r-v2-tool-card__label">{{ label }}</span>
      <span class="r-v2-tool-card__desc">{{ description }}</span>
    </span>
  </component>
</template>

<style scoped>
.r-v2-tool-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  flex: 1 1 0;
  min-width: 0;
  padding: 18px 18px 20px;
  border-radius: var(--r-radius-lg);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg);
  text-decoration: none;
  cursor: pointer;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-tool-card:hover {
  border-color: var(--r-color-border-strong);
  transform: translateY(-2px);
  box-shadow: 0 6px 18px color-mix(in srgb, black 16%, transparent);
}

.r-v2-tool-card--active {
  border-color: var(--r-color-brand-primary);
  background: color-mix(
    in srgb,
    var(--r-color-brand-primary) 12%,
    var(--r-color-bg-elevated)
  );
  box-shadow:
    0 6px 18px color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent),
    inset 0 0 0 1px
      color-mix(in srgb, var(--r-color-brand-primary) 40%, transparent);
}
.r-v2-tool-card--active:hover {
  /* Active card shouldn't lift — it's already the destination. Keeping
     the active card grounded helps the user read where they are. */
  transform: none;
}

.r-v2-tool-card--disabled {
  opacity: 0.55;
  cursor: not-allowed;
  pointer-events: none;
}

/* Icon medallion — circular pad so the glyph reads as a distinct
   element rather than a flat letter next to text. */
.r-v2-tool-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
  color: var(--r-color-fg-secondary);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-tool-card--active .r-v2-tool-card__icon {
  background: var(--r-color-brand-primary);
  color: white;
}

.r-v2-tool-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.r-v2-tool-card__label {
  font-size: 16px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  line-height: 1.2;
}
.r-v2-tool-card__desc {
  font-size: 12.5px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}

/* Modality-gated focus ring (key / pad) — matches the rest of v2. */
html[data-input="key"] .r-v2-tool-card:focus-visible,
html[data-input="pad"] .r-v2-tool-card:focus-visible {
  outline: 2px solid var(--r-color-brand-primary);
  outline-offset: 3px;
}
</style>
