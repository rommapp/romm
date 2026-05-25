<script setup lang="ts">
// ScanPlatform (v2) — one collapsible per scanning platform in the
// Scan view. Header shows the platform icon + name + per-platform
// chips (ROM count, firmware count, "not identified" badge).
//
// Body: lists every newly-scanned ROM via ScanPlatformRow, always
// inside an RVirtualScroller. Using the virtual scroller unconditionally
// keeps the body surface aligned with its content height regardless of
// the row count — an initial scan with hundreds of games per platform
// gets bounded DOM size, and small platforms still get the same flush
// surface (no late "growing into" the right shape as rows stream in).
import { RCollapsible, RPlatformIcon, RTag, RVirtualScroller } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import type { ScanningPlatform } from "@/stores/scanning";
import ScanPlatformRow from "@/v2/components/Scan/ScanPlatformRow.vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  platform: ScanningPlatform;
  /** Controlled open state — v-model:open from Scan.vue. */
  open?: boolean;
}>();

defineEmits<{
  (e: "update:open", value: boolean): void;
}>();

const { t } = useI18n();

// Row height baked into ScanPlatformRow's scoped styles (8px padding +
// 48px cover + 8px padding + 1px border). Kept here as a constant so
// `getItemHeight` and the row style stay in sync.
const ROW_HEIGHT = 65;
// Cap the virtual scroller's viewport so it never overruns the right
// pane. Up to this many rows render at natural height; above the cap
// the container scrolls internally.
const MAX_VIEWPORT_ROWS = 8;

// Use the natural cumulative height up to the cap so small / empty
// platforms don't show a tall empty box. Above the cap we lock to the
// max so streaming hundreds of rows can't push the panel off-screen.
const viewportHeight = computed(() => {
  const rows = Math.min(props.platform.roms.length, MAX_VIEWPORT_ROWS);
  // Always reserve at least one row's height so the body has visible
  // surface even when there are no ROMs yet (the "no new roms" empty
  // state still needs somewhere to sit).
  return Math.max(rows, 1) * ROW_HEIGHT;
});

function getItemHeight() {
  return ROW_HEIGHT;
}
</script>

<template>
  <RCollapsible
    :model-value="open"
    @update:model-value="(v) => $emit('update:open', v)"
  >
    <template #header-prepend>
      <RPlatformIcon
        v-if="platform.slug"
        :key="platform.slug"
        :slug="platform.slug"
        :name="platform.display_name"
        :size="32"
      />
    </template>
    <template #title>
      {{ platform.display_name }}
    </template>
    <template #header-append>
      <RTag tone="brand" size="x-small" :text="String(platform.roms.length)" />
      <RTag
        v-if="platform.firmware_count > 0"
        tone="warning"
        size="x-small"
        icon="mdi-memory"
        :text="String(platform.firmware_count)"
        :title="t('scan.firmware-found', platform.firmware_count)"
      />
      <RTag
        v-if="!platform.is_identified"
        tone="danger"
        size="small"
        icon="mdi-close"
        :text="t('scan.not-identified').toUpperCase()"
      />
    </template>

    <!-- Always virtualised — keeps the body surface flush with its
         content height regardless of how many rows have streamed in,
         and bounds the DOM size on big platforms. -->
    <div
      v-if="platform.roms.length === 0 && platform.firmware_count === 0"
      class="r-v2-scan-platform__empty"
    >
      {{ t("scan.no-new-roms") }}
    </div>
    <RVirtualScroller
      v-else
      :items="platform.roms"
      :get-item-height="getItemHeight"
      :height="viewportHeight"
      :overscan="10"
      class="r-v2-scan-platform__virtual"
    >
      <template #default="{ item }">
        <ScanPlatformRow :rom="item as SimpleRom" />
      </template>
    </RVirtualScroller>
  </RCollapsible>
</template>

<style scoped>
.r-v2-scan-platform__virtual {
  background: var(--r-color-bg-elevated);
  /* Top border so the first virtual row's border-top isn't the only
     visual boundary with the collapsible header. */
  border-top: 1px solid var(--r-color-border);
}
/* The first row inside the virtual scroller already paints a top
   border via ScanPlatformRow — collapse it so we don't double up the
   border thickness right under the collapsible header. */
.r-v2-scan-platform__virtual :deep(.r-v2-scan-platform__rom) {
  border-top: 1px solid var(--r-color-border);
}

.r-v2-scan-platform__empty {
  padding: 16px;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-size: 13px;
}
</style>
