<script setup lang="ts">
// CollectionListRow — single row of the Collections list-mode index.
//
// Anatomy mirrors GameListRow: cover mosaic + name on the left, kind
// chip in the middle, game count on the right. Click navigates with
// the same shared-element morph as CollectionTile so grid ↔ list ↔
// detail-page transitions land on the same animation anchor. Morph
// name includes the kind so regular/virtual/smart with overlapping
// numeric ids never collide.
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";
import { COLLECTION_LIST_GRID_TEMPLATE } from "./collectionListColumns";

defineOptions({ inheritAttrs: false });

type Kind = "regular" | "virtual" | "smart";

interface Props {
  id: number | string;
  name: string;
  romCount?: number;
  covers?: (string | null | undefined)[];
  to: string;
  kind?: Kind;
}

const props = withDefaults(defineProps<Props>(), {
  romCount: 0,
  covers: () => [],
  kind: "regular",
});

const { t } = useI18n();
const router = useRouter();
const coverEl = ref<HTMLElement | null>(null);
const { morphTransition } = useViewTransition();

const morphName = computed(() => `coll-cover-${props.kind}-${props.id}`);

const morphStyle = computed(() =>
  pendingMorphName.value === morphName.value
    ? { viewTransitionName: morphName.value }
    : undefined,
);

const kindLabel = computed(() =>
  props.kind === "smart" ? "Smart" : props.kind === "virtual" ? "Virtual" : "—",
);

const gridStyle = { gridTemplateColumns: COLLECTION_LIST_GRID_TEMPLATE };

function onRowClick(e: MouseEvent) {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  if (!coverEl.value) return;
  e.preventDefault();
  morphTransition({ el: coverEl.value, name: morphName.value }, async () => {
    await router.push(props.to);
  });
}
</script>

<template>
  <a
    class="coll-list-row"
    :style="gridStyle"
    :href="to"
    :aria-label="t('rom.open-game', { name })"
    @click="onRowClick"
  >
    <div class="coll-list-row__cell coll-list-row__title">
      <div ref="coverEl" class="coll-list-row__thumb" :style="morphStyle">
        <CollectionMosaic :covers="covers" />
      </div>
      <div class="coll-list-row__meta">
        <div class="coll-list-row__name">{{ name }}</div>
      </div>
    </div>

    <div class="coll-list-row__cell">
      <span
        class="coll-list-row__kind"
        :class="[`coll-list-row__kind--${kind}`]"
      >
        {{ kindLabel }}
      </span>
    </div>

    <div class="coll-list-row__cell coll-list-row__cell--end">
      {{ t("collection.games-count", romCount, { named: { n: romCount } }) }}
    </div>
  </a>
</template>

<style scoped>
.coll-list-row {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-secondary);
  text-decoration: none;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.coll-list-row:hover {
  background: var(--r-color-bg-elevated);
}

.coll-list-row:focus-visible {
  outline: none;
  background: var(--r-color-bg-elevated);
  box-shadow: inset 0 0 0 2px var(--r-color-brand-primary);
}

.coll-list-row__cell {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.coll-list-row__cell--end {
  display: flex;
  justify-content: flex-end;
}

.coll-list-row__title {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  min-width: 0;
}

.coll-list-row__thumb {
  width: var(--r-card-art-w-xs);
  height: var(--r-card-art-h-xs);
  flex-shrink: 0;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  background: var(--r-color-surface);
}

.coll-list-row__thumb :deep(.coll-mosaic) {
  width: 100%;
  height: 100%;
}

.coll-list-row__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.coll-list-row__name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.coll-list-row__kind {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}

.coll-list-row__kind--smart,
.coll-list-row__kind--virtual {
  color: var(--r-color-brand-primary);
}

.coll-list-row__count-unit {
  color: var(--r-color-fg-muted);
  margin-left: 4px;
}
</style>
