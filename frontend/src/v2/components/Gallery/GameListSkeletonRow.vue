<script setup lang="ts">
// GameListSkeletonRow — bootstrap-phase placeholder row for list-mode.
//
// Painted by `GalleryShell` while the first metadata window is in
// flight (no `total` yet). Self-contained: owns its row geometry +
// per-cell styles so the rendered shape matches a real `GameListRow`
// (same height, same grid template, same per-column skeleton shapes)
// without depending on `GameListRow`'s scoped CSS leaking into a
// sibling SFC. Mirrors the `GameCardSkeleton` pattern.
//
// `GameListRow` paints its own per-cell skeletons (when a row mounts
// before its position resolves) using the same per-column shapes, so
// both flavours stay visually identical.
import { RSkeletonBlock } from "@v2/lib";
import { computed } from "vue";
import {
  getListColumns,
  getListGridTemplate,
  LIST_COVER_HEIGHT_PX,
  LIST_COVER_WIDTH_PX,
} from "./listColumns";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Include the `platform` column. Defaults match `GameListHeader` /
   * `GameListRow` so the bootstrap-phase skeleton stays aligned with
   * whichever variant the surrounding list is rendering. */
  showPlatformColumn?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  showPlatformColumn: true,
});

const columns = computed(() => getListColumns(props.showPlatformColumn));
const gridStyle = computed(() => ({
  gridTemplateColumns: getListGridTemplate(props.showPlatformColumn),
}));
</script>

<template>
  <div class="r-glr-skel" :style="gridStyle">
    <template v-for="col in columns" :key="String(col.key)">
      <div v-if="col.key === 'select'" class="r-glr-skel__cell" />
      <div
        v-else-if="col.key === 'name'"
        class="r-glr-skel__cell r-glr-skel__title"
      >
        <RSkeletonBlock
          :width="LIST_COVER_WIDTH_PX"
          :height="LIST_COVER_HEIGHT_PX"
        />
        <div class="r-glr-skel__meta">
          <RSkeletonBlock width="60%" :height="12" />
          <RSkeletonBlock width="40%" :height="10" />
        </div>
      </div>

      <div v-else-if="col.key === 'platform_id'" class="r-glr-skel__cell">
        <div class="r-glr-skel__platform">
          <RSkeletonBlock :width="24" :height="24" circle />
          <RSkeletonBlock :width="100" :height="10" />
        </div>
      </div>

      <div
        v-else-if="col.key === 'languages' || col.key === 'regions'"
        class="r-glr-skel__cell"
      >
        <div class="r-glr-skel__pills">
          <RSkeletonBlock :width="28" :height="16" rounded="pill" />
          <RSkeletonBlock :width="28" :height="16" rounded="pill" />
        </div>
      </div>

      <div
        v-else-if="col.key === 'actions'"
        class="r-glr-skel__cell r-glr-skel__cell--end"
      >
        <RSkeletonBlock :width="18" :height="18" circle />
      </div>

      <div v-else class="r-glr-skel__cell">
        <RSkeletonBlock :width="col.skeletonWidth ?? 60" :height="10" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.r-glr-skel {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
}

.r-glr-skel__cell {
  min-width: 0;
}

.r-glr-skel__cell--end {
  display: flex;
  justify-content: flex-end;
}

.r-glr-skel__title {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  min-width: 0;
}

.r-glr-skel__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.r-glr-skel__pills {
  display: flex;
  gap: 3px;
}

.r-glr-skel__platform {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
</style>
