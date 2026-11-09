<script setup lang="ts">
// Primary-nav tab bar on sm-and-down, where AppNav drops its centre pill.
// Mount-gated (not `display: none`) so hidden links never take focus.
import { useI18n } from "vue-i18n";
import { useBreakpoint } from "@/composables/useBreakpoint";
import {
  NAV_ACTIVE_ICONS,
  useNavDestinations,
} from "@/composables/useNavDestinations";
import { RIcon, RSegmentedControl } from "@/lib";

const { t } = useI18n();
const { smAndDown } = useBreakpoint();
const { destinations, activeId } = useNavDestinations();

// Sticky avoids a Safari bug where fixed elements can get stuck after scrolling.
</script>

<template>
  <div v-if="smAndDown" class="r-bottom-nav-anchor">
    <nav class="r-bottom-nav" :aria-label="t('common.primary-navigation')">
      <RSegmentedControl
        :model-value="activeId"
        :items="destinations"
        variant="tab"
        class="r-bottom-nav__group"
      >
        <template #item="{ item, active }">
          <RIcon
            :icon="(active && NAV_ACTIVE_ICONS[item.id]) || item.icon"
            :size="28"
            :class="{
              'r-bottom-nav__icon--controller': item.icon === 'mdi-controller',
            }"
          />
          <span class="r-bottom-nav__label">{{ item.label }}</span>
        </template>
      </RSegmentedControl>
    </nav>
  </div>
</template>

<style scoped>
/* Matches .r-app-shell__body's height without adding to it; flex-end anchors the bar to sticky's bottom. */
.r-bottom-nav-anchor {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  pointer-events: none;
  z-index: 100;
}

/* Transparent strip; taps in its gutters fall through to the page. The
   safe-area inset keeps the bar above a notched phone's home indicator. */
.r-bottom-nav {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: center;
  padding: 8px var(--r-row-pad) calc(8px + var(--r-safe-b));
  pointer-events: none;
}

/* A dense frost, so busy cover art behind doesn't compete with the labels. */
.r-bottom-nav__group.r-segmented-control--tab {
  pointer-events: auto;
  flex: 1;
  box-sizing: border-box;
  max-width: var(--r-bottom-nav-max-w);
  padding: 5px;
  gap: 0;
  background: color-mix(in srgb, var(--r-color-bg) 62%, transparent);
  backdrop-filter: blur(24px);
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white 28%, transparent),
    inset 0 -1px 0 color-mix(in srgb, white 6%, transparent),
    inset 0 0 18px color-mix(in srgb, white 5%, transparent),
    var(--r-elev-2),
    var(--r-elev-1);
}

/* A translucent capsule, so the tinted icon + label carry the selection. */
.r-bottom-nav__group.r-segmented-control--tab.r-segmented-control--horizontal
  :deep(.r-segmented-control__indicator) {
  top: 5px;
  bottom: 5px;
  background: var(--r-color-surface-hover);
  box-shadow: inset 0 1px 0 color-mix(in srgb, white 12%, transparent);
}

.r-bottom-nav__group.r-segmented-control--tab :deep(.r-segmented-control__btn) {
  flex: 1;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  min-height: 52px;
  padding: 4px 2px;
}

.r-bottom-nav__group.r-segmented-control--tab
  :deep(.r-segmented-control__btn--active),
.r-bottom-nav__group.r-segmented-control--tab
  :deep(.r-segmented-control__btn--active:hover) {
  /* Pulled toward fg so the tint stays legible over a warm backdrop. */
  color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 75%,
    var(--r-color-fg)
  );
}

/* Mirrors the shared glass bar: reduced motion drops the costly blur. */
html.r-reduced-motion .r-bottom-nav__group.r-segmented-control--tab {
  background: var(--r-glass-bar-bg);
  backdrop-filter: var(--r-glass-bar-filter);
}

/* No hover fill on the bar; the primitive's press scale gives the feedback. */
.r-bottom-nav__group.r-segmented-control--tab
  :deep(
    .r-segmented-control__btn:hover:not(.r-segmented-control__btn--active)
  ) {
  background: transparent;
}

/* The controller glyph is wide and short and sits low in its box, so it
   is scaled and lifted to match the others' optical height and centre. */
.r-bottom-nav__icon--controller {
  transform: translateY(-1.3px) scale(1.2);
}

.r-bottom-nav__label {
  max-width: 100%;
  overflow: hidden;
  font-size: var(--r-font-size-sm);
  line-height: 1.2;
  letter-spacing: 0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
