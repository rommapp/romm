<script setup lang="ts">
// ScanPlatform (v2) — one collapsible per scanning platform in the
// Scan view. Header shows the platform icon + name + per-platform
// chips (ROM count, firmware count, "not identified" badge).
//
// Body: lists every newly-scanned ROM via ScanPlatformRow, rendered
// inside an RVirtualScroller whose viewport always equals the total
// content height. No internal scroll — the parent scan log handles
// overflow. The scroller stays in the loop anyway because its
// transform-based row positioning avoids reflowing existing rows
// as new ones stream in during a live scan.
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

// Viewport always matches the cumulative content height so the
// collapsible body grows naturally with the ROM list — no internal
// scroll. The parent scan log handles overflow. RVirtualScroller is
// still useful here because its `transform: translateY` positioning
// avoids reflowing existing rows as new ones stream in.
const viewportHeight = computed(() => {
  const rows = Math.max(props.platform.roms.length, 1);
  return rows * ROW_HEIGHT;
});

function getItemHeight() {
  return ROW_HEIGHT;
}

// Key rows by ROM id (not array index) so that prepending a freshly-scanned
// ROM — the lifecycle unshifts newest-first — only mounts the new row and
// lets the rest keep their DOM. Index keys would re-patch every row on each
// insert, killing the per-row entrance animation and flashing the list.
function getItemKey(item: unknown) {
  return (item as SimpleRom).id;
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
      :get-item-key="getItemKey"
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
/* Row separator is already painted by ScanPlatformRow's own
   `border-top`, so the virtual scroller itself stays chrome-less —
   no extra border or background would cause its content height to
   mismatch its inline `height:` style (border-box reserves the
   border out of the content area and triggers a spurious scroll). */
.r-v2-scan-platform__virtual {
  background: transparent;
}

.r-v2-scan-platform__empty {
  padding: 16px;
  text-align: center;
  color: var(--r-color-fg-muted);
  font-size: 13px;
}
</style>
