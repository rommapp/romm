<script setup lang="ts">
// PlatformHead — the platform-context strip that sits above the
// gallery / firmware / settings tab body. Composes the InfoPanel
// (icon + name + stats + provider chips + action ribbon) with the
// RTabNav. Re-used in two render branches inside Platform.vue:
//
//   1. Library tab — passed to `GalleryShell`'s `#header` slot so the
//      head scrolls naturally with the cards (and the toolbar pins
//      below it). Matches the pre-tabs experience.
//
//   2. Firmware / Settings tabs — rendered inline above the tab body
//      inside a plain scrollable wrapper. The head scrolls together
//      with the tab content so the user can move freely; switching
//      back to Library re-enters the gallery shell.
//
// All admin actions are forwarded as events; permission gating lives
// on the parent so the bar stays in sync with `useCan`.
import { RBtn, RChip, RPlatformIcon, RTabNav } from "@v2/lib";
import type { RTabNavItem } from "@v2/lib";
import type { Platform } from "@/stores/platforms";
import InfoPanel from "@/v2/components/Gallery/InfoPanel.vue";
import Stat from "@/v2/components/shared/Stat.vue";

defineOptions({ inheritAttrs: false });

interface StatRow {
  label: string;
  value: string;
}

interface ProviderChip {
  key: string;
  label: string;
  href: string | null;
  asset: string;
  title?: string;
}

defineProps<{
  platform: Platform;
  tab: string;
  tabs: RTabNavItem[];
  tags: string[];
  stats: StatRow[];
  providers: ProviderChip[];
  /** Permission flags — already evaluated against `useCan` in the
   *  parent so the buttons render in or out atomically with the rest
   *  of the page. */
  canEdit: boolean;
  canScan: boolean;
  canDelete: boolean;
  /** Label text — passed in so the parent owns i18n and this stays a
   *  presentational composite (no `useI18n` here). */
  labels: {
    edit: string;
    upload: string;
    scan: string;
    delete: string;
  };
  deleting?: boolean;
}>();

defineEmits<{
  (e: "update:tab", v: string): void;
  (e: "edit"): void;
  (e: "upload"): void;
  (e: "scan"): void;
  (e: "delete"): void;
}>();
</script>

<template>
  <InfoPanel :title="platform.display_name">
    <template #cover>
      <div
        class="r-v2-plat__panel-icon"
        :style="{ viewTransitionName: `platform-icon-${platform.id}` }"
      >
        <RPlatformIcon
          :slug="platform.slug"
          :fs-slug="platform.fs_slug"
          :alt="platform.display_name"
          :size="148"
        />
      </div>
    </template>

    <template v-if="tags.length" #tags>
      <RChip
        v-for="tag in tags"
        :key="tag"
        size="small"
        variant="translucent"
        :rounded="20"
      >
        {{ tag }}
      </RChip>
    </template>

    <template v-if="stats.length" #stats>
      <Stat
        v-for="s in stats"
        :key="s.label"
        :value="s.value"
        :label="s.label"
      />
    </template>

    <template v-if="providers.length" #providers>
      <a
        v-for="chip in providers"
        :key="chip.key"
        :href="chip.href ?? undefined"
        :target="chip.href ? '_blank' : undefined"
        rel="noopener noreferrer"
        :title="chip.title"
        class="r-v2-plat__provider"
        :class="{
          'r-v2-plat__provider--passive': !chip.href,
          'r-v2-plat__provider--icon-only': !chip.label,
        }"
      >
        <img
          :src="chip.asset"
          :alt="chip.title ?? chip.key"
          class="r-v2-plat__provider-logo"
        />
        <span v-if="chip.label" class="r-v2-plat__provider-label">
          {{ chip.label }}
        </span>
      </a>
    </template>

    <!-- Action ribbon — Edit / Upload / Scan / Delete. Same circular
         icon-button vocabulary as the GameDetails action row. Tooltips
         ride RBtn's built-in `tooltip` prop (the default slot is
         dropped on icon-only buttons). -->
    <template #actions>
      <RBtn
        v-if="canEdit"
        variant="outlined"
        surface
        icon="mdi-pencil-outline"
        rounded="circle"
        :aria-label="labels.edit"
        :tooltip="labels.edit"
        @click="$emit('edit')"
      />
      <RBtn
        v-if="canEdit"
        variant="outlined"
        surface
        icon="mdi-cloud-upload-outline"
        rounded="circle"
        :aria-label="labels.upload"
        :tooltip="labels.upload"
        @click="$emit('upload')"
      />
      <RBtn
        v-if="canScan"
        variant="outlined"
        surface
        icon="mdi-magnify-scan"
        rounded="circle"
        :aria-label="labels.scan"
        :tooltip="labels.scan"
        @click="$emit('scan')"
      />
      <RBtn
        v-if="canDelete"
        variant="outlined"
        surface
        color="danger"
        icon="mdi-delete-outline"
        rounded="circle"
        :aria-label="labels.delete"
        :tooltip="labels.delete"
        :disabled="deleting"
        :loading="deleting"
        @click="$emit('delete')"
      />
    </template>
  </InfoPanel>

  <RTabNav
    :model-value="tab"
    :items="tabs"
    class="r-v2-plat__tabs"
    @update:model-value="(v) => $emit('update:tab', v)"
  />
</template>

<style scoped>
.r-v2-plat__panel-icon {
  width: 200px;
  height: 148px;
  display: grid;
  place-items: center;
}

html[data-bp~="xs"] .r-v2-plat__panel-icon {
  width: 80px;
  height: 60px;
}
html[data-bp~="xs"] .r-v2-plat__panel-icon :deep(.r-platform-icon) {
  width: 100% !important;
  height: 100% !important;
}

.r-v2-plat__tabs {
  /* Tuck the nav up against the InfoPanel's bottom padding so the
     two read as a single head band. */
  margin-top: -8px;
}

/* ── Provider chip cluster ───────────────────────────────────────
   Compact pill that pairs the provider's logo with its remote ID.
   `--passive` (Flashpoint / HLTB / Libretro — no public lookup URL)
   drops the hover lift since clicking does nothing. */
.r-v2-plat__provider {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px 2px 4px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-secondary);
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  font-variant-numeric: tabular-nums;
  text-decoration: none;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-plat__provider:hover:not(.r-v2-plat__provider--passive) {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
  color: var(--r-color-fg);
  transform: translateY(-1px);
}
.r-v2-plat__provider--passive {
  cursor: default;
  pointer-events: none;
}
.r-v2-plat__provider--icon-only {
  padding: 2px 4px;
}
.r-v2-plat__provider-logo {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  object-fit: contain;
  flex-shrink: 0;
}
.r-v2-plat__provider-label {
  white-space: nowrap;
}
</style>
