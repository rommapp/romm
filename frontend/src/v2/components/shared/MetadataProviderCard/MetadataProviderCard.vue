<script setup lang="ts">
// MetadataProviderCard: the one card every metadata-provider surface
// renders (settings tiles, setup wizard step, scan reference dialog).
// Two layouts:
//   • tile, vertical: circular logo + name + status chip in the
//     header, `#actions` footer pinned to the bottom edge so cards
//     stretched by an equal-height grid row never leave a gap under it.
//   • row, horizontal: square logo beside name, description and
//     setup / caveat pills; the status chip joins the pill row.
// Surface-specific state styling (e.g. the wizard's "available" tint)
// stays in the consumer, keyed on a data-* attr it passes through.
import { RIcon, RImg, RTag } from "@v2/lib";
import type { ProviderCardStatus } from "./types";

defineOptions({ inheritAttrs: false });

interface Props {
  name: string;
  /** Logo path under /assets/scrappers/. */
  logo: string;
  layout?: "tile" | "row";
  /** Element rendering the name. Consumers whose surface is navigated
   *  by headings (the scan reference dialog) pass a heading level. */
  nameTag?: "span" | "h3" | "h4";
  /** Small uppercase descriptor under the name (tile layout). */
  subtitle?: string;
  status?: ProviderCardStatus;
  /** Mono pill with the env-var / config instructions. */
  setupHint?: string;
  /** Warning-tinted pill for a provider caveat. */
  caveat?: string;
  /** Faded look for a provider that is disabled / not configured. */
  dimmed?: boolean;
}

withDefaults(defineProps<Props>(), {
  layout: "tile",
  nameTag: "span",
  subtitle: undefined,
  status: undefined,
  setupHint: undefined,
  caveat: undefined,
  dimmed: false,
});

defineSlots<{
  /** Body prose: the provider description. */
  description?: () => unknown;
  /** Footer actions (buttons / links). Pinned to the bottom in tile
   *  layout, full-width below the body in row layout. */
  actions?: () => unknown;
}>();
</script>

<template>
  <article
    v-bind="$attrs"
    class="r-provider-card"
    :class="[
      `r-provider-card--${layout}`,
      { 'r-provider-card--dimmed': dimmed },
    ]"
  >
    <header class="r-provider-card__header">
      <div class="r-provider-card__logo">
        <!-- Decorative: the name sits right next to it. -->
        <RImg :src="logo" alt="" width="100%" height="100%" contain />
      </div>
      <div class="r-provider-card__head-text">
        <component :is="nameTag" class="r-provider-card__name">
          {{ name }}
        </component>
        <span v-if="subtitle" class="r-provider-card__subtitle">
          {{ subtitle }}
        </span>
        <RTag
          v-if="status && layout === 'tile'"
          :tone="status.tone"
          :prepend-icon="status.icon"
          :text="status.label"
          size="x-small"
        />
      </div>
    </header>

    <div
      v-if="
        $slots.description ||
        setupHint ||
        caveat ||
        (status && layout === 'row')
      "
      class="r-provider-card__body"
    >
      <p v-if="$slots.description" class="r-provider-card__desc">
        <slot name="description" />
      </p>
      <div
        v-if="setupHint || caveat || (status && layout === 'row')"
        class="r-provider-card__meta"
      >
        <span v-if="setupHint" class="r-provider-card__pill">
          <RIcon icon="mdi-cog-outline" size="11" />
          {{ setupHint }}
        </span>
        <span
          v-if="caveat"
          class="r-provider-card__pill r-provider-card__pill--warn"
        >
          <RIcon icon="mdi-alert-circle-outline" size="11" />
          {{ caveat }}
        </span>
        <RTag
          v-if="status && layout === 'row'"
          :tone="status.tone"
          :prepend-icon="status.icon"
          :text="status.label"
          size="small"
        />
      </div>
    </div>

    <footer v-if="$slots.actions" class="r-provider-card__actions">
      <slot name="actions" />
    </footer>
  </article>
</template>

<style scoped>
/* ── Shell: bg + radius + overflow hidden so the footer's border-top
   reaches the rounded corners cleanly. ─────────────────────────────── */
.r-provider-card {
  border-radius: var(--r-radius-md);
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  overflow: hidden;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-provider-card--dimmed {
  opacity: 0.75;
}

.r-provider-card__name {
  margin: 0;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
}

.r-provider-card__subtitle {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--r-font-weight-semibold);
}

.r-provider-card__desc {
  margin: 0;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  line-height: var(--r-line-height-normal);
}

.r-provider-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-1);
  margin-top: var(--r-space-1);
}

.r-provider-card__pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  font-family:
    var(--r-font-family-mono, ui-monospace), SFMono-Regular, monospace;
}
.r-provider-card__pill--warn {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 14%,
    transparent
  );
  border-color: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 36%,
    transparent
  );
  color: var(--r-color-warning);
  font-family: inherit;
}

.r-provider-card__actions {
  display: flex;
  gap: var(--r-space-2);
  padding: 12px 14px;
  border-top: 1px solid var(--r-color-border);
  background: var(--r-color-bg-elevated);
}

/* ── Tile layout: flex column so the footer can pin to the bottom
   edge when the grid row stretches the card. ───────────────────────── */
.r-provider-card--tile {
  display: flex;
  flex-direction: column;
}
.r-provider-card--tile .r-provider-card__header {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: 16px 16px 14px;
}
.r-provider-card--tile .r-provider-card__logo {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  padding: 6px;
}
.r-provider-card--tile .r-provider-card__head-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.r-provider-card--tile .r-provider-card__name {
  font-size: 14px;
}
.r-provider-card--tile .r-provider-card__body {
  padding: 0 16px 14px;
}
.r-provider-card--tile .r-provider-card__actions {
  margin-top: auto;
}

/* ── Row layout: logo column beside a name / description / pills
   stack. The header dissolves into the grid so the body lines up
   under the name, not under the logo. ──────────────────────────────── */
.r-provider-card--row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  align-items: start;
  column-gap: var(--r-space-3);
  row-gap: 2px;
  padding: var(--r-space-3) var(--r-space-4);
}
.r-provider-card--row .r-provider-card__header {
  display: contents;
}
.r-provider-card--row .r-provider-card__logo {
  width: 36px;
  height: 36px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  padding: 2px;
}
.r-provider-card--row .r-provider-card__head-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-provider-card--row .r-provider-card__name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
}
.r-provider-card--row .r-provider-card__body {
  grid-column: 2;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-provider-card--row .r-provider-card__actions {
  grid-column: 1 / -1;
}
</style>
