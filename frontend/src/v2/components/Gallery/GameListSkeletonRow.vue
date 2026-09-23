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
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import {
  getListColumns,
  getListGridTemplate,
  LIST_COVER_HEIGHT_PX,
  LIST_COVER_WIDTH_PX,
  LIST_TITLE_SKELETON_BARS,
  LIST_TITLE_SKELETON_GAP_PX,
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
const titleGapStyle = { gap: `${LIST_TITLE_SKELETON_GAP_PX}px` };

// Phones and tablets render the compact two-line row, so the placeholder
// follows it instead of the columns.
const { smAndDown } = useBreakpoint();
</script>

<template>
  <div v-if="smAndDown" class="r-glr-skel r-glr-skel--compact r-list-compact">
    <!-- Stands in for the compact row's tick column, or the cover would start
         further left here than in the row this replaces. -->
    <div class="r-glr-skel__select" />
    <div class="r-glr-skel__cell r-glr-skel__cover">
      <RSkeletonBlock
        :width="LIST_COVER_WIDTH_PX"
        :height="LIST_COVER_HEIGHT_PX"
      />
    </div>
    <div class="r-list-compact__stack" :style="titleGapStyle">
      <RSkeletonBlock
        v-for="(bar, i) in LIST_TITLE_SKELETON_BARS"
        :key="i"
        :width="bar.width"
        :height="bar.height"
      />
    </div>
  </div>

  <div v-else class="r-glr-skel r-glr-skel--columns" :style="gridStyle">
    <template v-for="col in columns" :key="String(col.key)">
      <div v-if="col.key === 'select'" class="r-glr-skel__cell" />
      <div
        v-else-if="col.key === 'cover'"
        class="r-glr-skel__cell r-glr-skel__cover"
      >
        <RSkeletonBlock
          :width="LIST_COVER_WIDTH_PX"
          :height="LIST_COVER_HEIGHT_PX"
        />
      </div>
      <div
        v-else-if="col.key === 'name'"
        class="r-glr-skel__cell r-glr-skel__title"
      >
        <div class="r-glr-skel__meta" :style="titleGapStyle">
          <RSkeletonBlock
            v-for="(bar, i) in LIST_TITLE_SKELETON_BARS"
            :key="i"
            :width="bar.width"
            :height="bar.height"
          />
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

      <div
        v-else
        class="r-glr-skel__cell"
        :class="{ 'r-glr-skel__cell--end': col.align === 'end' }"
      >
        <RSkeletonBlock :width="col.skeletonWidth ?? 60" :height="10" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.r-glr-skel {
  /* Bleeds with the row it stands in for (see GameListRow). */
  margin-inline: calc(-1 * var(--r-list-bleed, 0px));
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-5);
  padding: 0 var(--r-space-3);
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
}
.r-glr-skel--columns {
  margin-inline-start: calc(-1 * var(--r-list-bleed-start, 0px));
  padding-inline-start: var(--r-list-bleed-start, var(--r-space-3));
}

.r-glr-skel--compact > .r-glr-skel__select {
  flex: none;
  width: var(--r-list-select-w);
}

.r-glr-skel__cell {
  min-width: 0;
}

/* Placeholders sit on the same edge as the value they stand in for, so
   nothing shifts when the row hydrates. */
.r-glr-skel__cell--end {
  text-align: end;
}

/* Centre the cover block to match the real row. */
.r-glr-skel__cover {
  display: flex;
  align-items: center;
  justify-content: center;
}

.r-glr-skel__title {
  display: flex;
  align-items: center;
  min-width: 0;
}

.r-glr-skel__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
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
