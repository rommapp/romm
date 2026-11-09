<script setup lang="ts">
// BottomNav: the primary-navigation tab bar, pinned to the bottom edge on
// sm-and-down so the four destinations sit within thumb reach (AppNav drops
// its centre pill there). A floating glass bar with stacked icon + label
// tabs, built on RSegmentedControl so routing, the sliding active capsule
// and keyboard / gamepad roving come from the primitive.
//
// Mount-gated on the breakpoint ref (not `display: none`) so the router
// links never sit hidden-but-focusable in the tab order on larger viewports.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useBreakpoint } from "@/composables/useBreakpoint";
import { useNavDestinations } from "@/composables/useNavDestinations";
import { RIcon, RSegmentedControl } from "@/lib";

const { t } = useI18n();
const { smAndDown } = useBreakpoint();
const { destinations, activeId } = useNavDestinations();

const activeIcons = computed(
  () => new Map(destinations.value.map((d) => [d.id, d.activeIcon])),
);

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
            :icon="active ? activeIcons.get(item.id) : item.icon"
            :size="26"
            class="r-bottom-nav__icon"
            :class="`r-bottom-nav__icon--${item.id}`"
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

/* Boosted saturation lets the content behind bleed through as colour. */
.r-bottom-nav__group.r-segmented-control--tab {
  pointer-events: auto;
  flex: 1;
  box-sizing: border-box;
  max-width: var(--r-bottom-nav-max-w);
  padding: 5px;
  gap: 0;
  background: color-mix(in srgb, var(--r-color-bg) 42%, transparent);
  border: 1px solid color-mix(in srgb, white 14%, transparent);
  backdrop-filter: blur(24px) saturate(190%) brightness(1.06);
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, white 28%, transparent),
    inset 0 -1px 0 color-mix(in srgb, white 6%, transparent),
    inset 0 0 18px color-mix(in srgb, white 5%, transparent),
    0 10px 30px color-mix(in srgb, black 35%, transparent),
    0 2px 8px color-mix(in srgb, black 18%, transparent);
}

/* Active capsule: a translucent lens rather than the solid white pill the
   top nav uses, so the tinted icon + label carry the selection. */
.r-bottom-nav__group :deep(.r-segmented-control__indicator) {
  top: 5px;
  bottom: 5px;
  background: color-mix(in srgb, var(--r-color-fg) 12%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, white 12%, transparent);
}

.r-bottom-nav__group :deep(.r-segmented-control__btn) {
  flex: 1;
  flex-direction: column;
  justify-content: center;
  gap: 2px;
  min-height: 52px;
  padding: 4px 2px;
  color: var(--r-color-fg-secondary);
  font-weight: var(--r-font-weight-medium);
}

.r-bottom-nav__group :deep(.r-segmented-control__btn--active),
.r-bottom-nav__group :deep(.r-segmented-control__btn--active:hover) {
  /* Pulled toward fg so the tint stays legible over a warm backdrop. */
  color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 75%,
    var(--r-color-fg)
  );
  font-weight: var(--r-font-weight-semibold);
}

/* Mirrors the shared glass bar: reduced motion drops the costly blur. */
:global(html.r-reduced-motion) .r-bottom-nav__group.r-segmented-control--tab {
  background: var(--r-glass-bar-bg);
  backdrop-filter: var(--r-glass-bar-filter);
}

/* Touch has no hover; the press scale is the only feedback needed. */
.r-bottom-nav__group
  :deep(
    .r-segmented-control__btn:hover:not(.r-segmented-control__btn--active)
  ) {
  background: transparent;
}

/* The controller glyph is wide and short and sits low in its box, so it
   is scaled and lifted to match the others' optical height and centre. */
.r-bottom-nav__icon--platforms {
  transform: translateY(-1.3px) scale(1.2);
}

.r-bottom-nav__label {
  max-width: 100%;
  overflow: hidden;
  font-size: 10.5px;
  line-height: 1.2;
  letter-spacing: 0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
