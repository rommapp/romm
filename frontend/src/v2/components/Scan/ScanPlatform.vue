<script setup lang="ts">
// ScanPlatform (v2) — one collapsible per scanning platform in the
// Scan view. Header shows the platform icon + name + per-platform
// chips (ROM count, firmware count, "not identified" badge).
//
// Body: lists every newly-scanned ROM via ScanPlatformRow. Switches to
// RVirtualScroller once the ROM count crosses VIRT_THRESHOLD so an
// initial scan with hundreds of games per platform keeps the DOM size
// bounded and scroll smooth. The threshold is high enough that small
// platforms keep the natural inline layout (no fixed-height scroll
// box), and low enough that big platforms get virtualised before the
// browser starts struggling.
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

// Above this row count, the body switches to the virtual scroller with
// a bounded viewport. Below it, we keep the plain inline list so small
// platforms don't get a redundant scrollbar.
const VIRT_THRESHOLD = 50;
// Row height baked into ScanPlatformRow's scoped styles (8px padding +
// 48px cover + 8px padding + 1px border). Kept here as a constant so
// `getItemHeight` and the row style stay in sync.
const ROW_HEIGHT = 65;
// Bounded viewport for the virtualised list — tall enough to read a
// real chunk of the scan, short enough that the parent log can still
// show neighbour platforms above and below.
const VIRT_VIEWPORT_PX = 480;

const shouldVirtualise = computed(
  () => props.platform.roms.length >= VIRT_THRESHOLD,
);

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

    <!-- Virtualised path — only when the platform has crossed the
         threshold. RVirtualScroller absolutely positions each row, so
         we wrap it in our own surface (background, top border) instead
         of leaning on the <ul> styling. -->
    <RVirtualScroller
      v-if="shouldVirtualise"
      :items="platform.roms"
      :get-item-height="getItemHeight"
      :height="VIRT_VIEWPORT_PX"
      :overscan="10"
      class="r-v2-scan-platform__virtual"
    >
      <template #default="{ item }">
        <ScanPlatformRow :rom="item as SimpleRom" />
      </template>
    </RVirtualScroller>

    <!-- Plain path — small platforms keep the natural inline list. -->
    <ul v-else class="r-v2-scan-platform__rom-list">
      <li v-for="rom in platform.roms" :key="rom.id">
        <ScanPlatformRow :rom="rom" />
      </li>
      <li
        v-if="platform.roms.length === 0 && platform.firmware_count === 0"
        class="r-v2-scan-platform__empty"
      >
        {{ t("scan.no-new-roms") }}
      </li>
    </ul>
  </RCollapsible>
</template>

<style scoped>
.r-v2-scan-platform__rom-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--r-color-bg-elevated);
}

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
