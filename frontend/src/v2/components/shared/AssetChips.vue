<script setup lang="ts">
// The facts shared by every save and state row or tile: newest-in-its-group
// tag, emulator tag and file size, in one wrapping row.
import { RIcon, RTag } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { useStreamingStore } from "@/stores/streaming";
import { formatBytes } from "@/utils";
import type { Asset } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    asset: Asset;
    /** Newest of several versions in its slot or core. */
    latest?: boolean;
    /** Off where the emulator is already the group's title. */
    showEmulator?: boolean;
  }>(),
  { latest: false, showEmulator: true },
);

const { t } = useI18n();
const { emulatorLabel } = useStreamingStore();
</script>

<template>
  <span class="r-asset-chips" v-bind="$attrs">
    <RTag
      v-if="latest"
      tone="brand"
      size="x-small"
      :text="t('play.latest-version')"
    />
    <RTag
      v-if="showEmulator && asset.emulator"
      tone="warning"
      size="x-small"
      :text="emulatorLabel(asset.emulator)"
    />
    <span class="r-asset-chips__size">
      <RIcon icon="mdi-weight" size="11" />
      {{ formatBytes(asset.file_size_bytes) }}
    </span>
  </span>
</template>

<style scoped>
.r-asset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.r-asset-chips__size {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 10px;
  color: var(--r-color-fg-secondary);
}
</style>
