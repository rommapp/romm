<script setup lang="ts">
// Primary-nav tab bar on sm-and-down, where AppNav drops its centre pill.
// Mount-gated (not `display: none`) so hidden links never take focus.
import { computed, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { useBreakpoint } from "@/composables/useBreakpoint";
import {
  NAV_FILLED_ICONS,
  useNavDestinations,
} from "@/composables/useNavDestinations";
import type { NavDestinationId } from "@/composables/useNavDestinations";
import { RIcon, RSegmentedControl } from "@/lib";
import { skipTransitionTo } from "@/plugins/transition";

const { t } = useI18n();
const { smAndDown } = useBreakpoint();
const { destinations, activeId } = useNavDestinations();
const router = useRouter();

// The route updates only after the lazy view loads and the view transition is captured.
const pendingId = ref<NavDestinationId | null>(null);
const shownId = computed(() => pendingId.value ?? activeId.value);

// Runs in the capture phase: a loaded view navigates inside RouterLink's own handler.
function onTap(event: MouseEvent) {
  // RouterLink leaves these clicks to the browser, so no navigation follows.
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const href = (event.target as HTMLElement | null)
    ?.closest("a")
    ?.getAttribute("href");
  const tapped = destinations.value.find((d) => d.to === href);
  if (!tapped) return;
  pendingId.value = tapped.id;
  skipTransitionTo(tapped.to);
}

// Only the latest navigation may clear the highlight; a superseded one finishes on its own.
let latestPath: string | null = null;
const stopTracking = router.beforeEach((to) => {
  latestPath = to.fullPath;
});
const settle = (to: { fullPath: string }) => {
  if (to.fullPath === latestPath) pendingId.value = null;
};
const stopSettled = router.afterEach((to) => settle(to));
// Errors such as a rejected lazy import skip afterEach.
const stopOnError = router.onError((_error, to) => settle(to));
onBeforeUnmount(() => {
  stopTracking();
  stopSettled();
  stopOnError();
});

// Sticky avoids a Safari bug where fixed elements can get stuck after scrolling.
</script>

<template>
  <div v-if="smAndDown" class="r-bottom-nav-anchor">
    <nav class="r-bottom-nav" :aria-label="t('common.primary-navigation')">
      <RSegmentedControl
        :model-value="shownId"
        :items="destinations"
        variant="tab"
        class="r-bottom-nav__group"
        @click.capture="onTap"
      >
        <template #item="{ item }">
          <RIcon
            :icon="NAV_FILLED_ICONS[item.id] ?? item.icon"
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
  /* Below the top bar (100), or iOS Safari won't tint the status bar from it. */
  z-index: 99;
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

/* A narrower gutter than the page's, so four labels fit on a 320px phone. */
html[data-bp~="xs"] .r-bottom-nav {
  padding-inline: 10px;
}

/* A dense frost, so busy cover art behind doesn't compete with the labels. */
.r-bottom-nav__group.r-segmented-control--tab {
  pointer-events: auto;
  flex: 1;
  box-sizing: border-box;
  max-width: var(--r-bottom-nav-max-w);
  padding: 4px;
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
  top: 4px;
  bottom: 4px;
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
  padding: 4px 6px;
  touch-action: manipulation;
  container-type: inline-size;
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

/* Shrinks toward 10px on the narrowest phones so the labels still fit. */
.r-bottom-nav__label {
  max-width: 100%;
  overflow: hidden;
  font-size: clamp(10px, 16.5cqi, var(--r-font-size-sm));
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
