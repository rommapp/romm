<script setup lang="ts">
// PlatformTile — platform card used by the Home dashboard row (variant="row",
// 150px fixed) and the /platforms grid (variant="grid"). Feature composite
// around RPlatformIcon; not a design-system primitive.
import { RPlatformIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import {
  playableTooltip,
  usePlatformPlayable,
} from "@/v2/composables/usePlatformPlayable";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";

defineOptions({ inheritAttrs: false });

type Variant = "row" | "grid";

interface Props {
  /** Platform slug used to locate /assets/platforms/<slug>.{svg,ico} */
  slug: string;
  /** Filesystem slug (tried first — matches v1's fallback chain). */
  fsSlug?: string;
  displayName: string;
  romCount?: number | null;
  /** Override destination; otherwise derived from `id`. */
  to?: string | object;
  id?: number | string;
  variant?: Variant;
}

const props = withDefaults(defineProps<Props>(), {
  fsSlug: undefined,
  romCount: null,
  to: undefined,
  id: undefined,
  variant: "row",
});

const href = computed(() => props.to ?? `/platform/${props.id ?? ""}`);

// Shared-element morph between the platform tile icon and the
// RPlatformIcon shown in the Platform view's InfoPanel cover slot.
const router = useRouter();
const iconEl = ref<HTMLElement | null>(null);
const { morphTransition } = useViewTransition();

const morphName = computed(() =>
  props.id != null ? `platform-icon-${props.id}` : null,
);

function onTileClick(e: MouseEvent) {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  if (!iconEl.value || !morphName.value) return;
  const target = href.value;
  if (typeof target !== "string") return;
  e.preventDefault();
  morphTransition({ el: iconEl.value, name: morphName.value }, async () => {
    await router.push(target);
  });
}

const morphStyle = computed(() =>
  morphName.value && pendingMorphName.value === morphName.value
    ? { viewTransitionName: morphName.value }
    : undefined,
);

const { playable, emulator } = usePlatformPlayable(() => props.slug);
const playableLabel = computed(() => playableTooltip(emulator.value));
</script>

<template>
  <router-link
    :to="href"
    v-bind="$attrs"
    class="plat-tile"
    :class="[`plat-tile--${variant}`]"
    @click="onTileClick"
  >
    <div ref="iconEl" class="plat-tile__icon" :style="morphStyle">
      <RPlatformIcon
        :slug="slug"
        :fs-slug="fsSlug"
        :alt="displayName"
        :size="72"
        :show-tooltip="false"
      />
    </div>
    <span v-if="playable" class="plat-tile__playable">
      <RIcon icon="mdi-play-circle" size="16" />
      <RTooltip activator="parent" :text="playableLabel" location="top" />
    </span>
    <div class="plat-tile__name">
      {{ displayName }}
    </div>
    <div v-if="romCount != null" class="plat-tile__count">
      {{ romCount }} {{ romCount === 1 ? "game" : "games" }}
    </div>
  </router-link>
</template>

<style scoped>
.plat-tile {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 16px 18px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  color: var(--r-color-fg-secondary);
  text-decoration: none;
  cursor: pointer;
  transition:
    background var(--r-motion-fast),
    border-color var(--r-motion-fast),
    transform var(--r-motion-fast);
}

.plat-tile:hover,
.plat-tile:focus-visible {
  background: var(--r-color-surface);
  border-color: var(--r-color-border-strong);
  transform: translateY(-2px);
}

/* Keyboard / gamepad focus — stronger border + stacked brand glow so
   the focused tile reads distinctly from a hover. */
.plat-tile:focus-visible {
  border-color: var(--r-color-brand-primary);
  box-shadow:
    0 8px 28px color-mix(in srgb, black 35%, transparent),
    0 0 0 2px var(--r-color-brand-primary),
    0 0 18px color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
  outline: none;
}

.plat-tile--row {
  width: 150px;
  flex-shrink: 0;
}

.plat-tile__icon {
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  opacity: 0.9;
  transition: opacity var(--r-motion-fast);
}

.plat-tile__playable {
  position: absolute;
  right: 8px;
  top: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-success);
}

.plat-tile:hover .plat-tile__icon {
  opacity: 1;
}

.plat-tile__name {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  text-align: center;
  line-height: 1.35;
}

.plat-tile__count {
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

html[data-bp~="xs"] .plat-tile--row {
  width: 110px;
}
html[data-bp~="xs"] .plat-tile {
  padding: 12px 8px 10px;
  gap: 6px;
}
html[data-bp~="xs"] .plat-tile__icon {
  width: 52px;
  height: 52px;
}
html[data-bp~="xs"] .plat-tile__name {
  font-size: 10px;
}
html[data-bp~="xs"] .plat-tile__count {
  font-size: 9px;
}
</style>
