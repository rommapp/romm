<script setup lang="ts">
// CollectionTile — collection card (Home row + /collections grid). Feature
// composite that wraps CollectionMosaic + name + count. `kind` overlays
// "Smart" or "Virtual" badge. `variant` controls sizing ("row" = 150px
// fixed, "grid" = fills cell).
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import CollectionMosaic from "@/v2/components/Collections/CollectionMosaic.vue";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";

defineOptions({ inheritAttrs: false });

type Variant = "row" | "grid";
type Kind = "regular" | "virtual" | "smart";

interface Props {
  name: string;
  romCount?: number;
  covers?: (string | null | undefined)[];
  to: string | object;
  variant?: Variant;
  kind?: Kind;
  /** Stable id used to derive the shared-element morph tag. Optional —
   *  if absent the tile still navigates but won't participate in the
   *  morph (some callers pass a virtual/smart wrapper object). */
  id?: number | string;
}

const props = withDefaults(defineProps<Props>(), {
  romCount: 0,
  covers: () => [],
  variant: "row",
  kind: "regular",
  id: undefined,
});

const { t } = useI18n();

const kindLabel = computed(() =>
  props.kind === "smart" ? "Smart" : props.kind === "virtual" ? "Virtual" : "",
);

// Shared-element morph between the tile's CollectionMosaic and the
// CollectionMosaic shown in the Collection view's InfoPanel cover slot.
// The tag includes the kind so regular/virtual/smart with overlapping
// numeric ids can never collide.
const router = useRouter();
const coverEl = ref<HTMLElement | null>(null);
const { morphTransition } = useViewTransition();

const morphName = computed(() =>
  props.id != null ? `coll-cover-${props.kind}-${props.id}` : null,
);

function onTileClick(e: MouseEvent) {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  if (!coverEl.value || !morphName.value) return;
  if (typeof props.to !== "string") return;
  e.preventDefault();
  const target = props.to;
  morphTransition({ el: coverEl.value, name: morphName.value }, async () => {
    await router.push(target);
  });
}

const morphStyle = computed(() =>
  morphName.value && pendingMorphName.value === morphName.value
    ? { viewTransitionName: morphName.value }
    : undefined,
);
</script>

<template>
  <router-link
    :to="to"
    v-bind="$attrs"
    class="coll-tile"
    :class="[`coll-tile--${variant}`]"
    @click="onTileClick"
  >
    <div ref="coverEl" class="coll-tile__cover" :style="morphStyle">
      <CollectionMosaic :covers="covers" />
      <span v-if="kindLabel" class="coll-tile__kind">{{ kindLabel }}</span>
    </div>
    <div class="coll-tile__name">
      {{ name }}
    </div>
    <div class="coll-tile__count">
      {{ t("collection.games-count", romCount, { named: { n: romCount } }) }}
    </div>
  </router-link>
</template>

<style scoped>
.coll-tile {
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: var(--r-color-fg);
  text-decoration: none;
  cursor: pointer;
}

.coll-tile--row {
  width: 150px;
  flex-shrink: 0;
}

.coll-tile__cover {
  position: relative;
  box-shadow: var(--r-elev-1);
  border-radius: var(--r-radius-lg);
  overflow: hidden;
  transition:
    transform var(--r-motion-fast),
    box-shadow var(--r-motion-fast);
}

.coll-tile:hover .coll-tile__cover,
.coll-tile:focus-visible .coll-tile__cover {
  transform: translateY(-2px);
  box-shadow: var(--r-elev-2);
}

/* Keyboard / gamepad focus — ring + brand glow on the cover, brighten
   the name. Matches the v1 console card visual language. */
.coll-tile:focus-visible {
  outline: none;
}
.coll-tile:focus-visible .coll-tile__cover {
  box-shadow:
    0 8px 28px color-mix(in srgb, black 40%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
}
.coll-tile:focus-visible .coll-tile__name {
  color: var(--r-color-fg);
}

.coll-tile__kind {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 8px;
  border-radius: var(--r-radius-chip);
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: color-mix(
    in srgb,
    var(--r-color-brand-primary-hover) 85%,
    transparent
  );
  color: var(--r-color-overlay-fg);
}

.coll-tile__name {
  font-size: 12.5px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
  padding: 0 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.coll-tile__count {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  padding: 0 2px;
}

html[data-bp~="xs"] .coll-tile--row {
  width: 120px;
}
</style>
