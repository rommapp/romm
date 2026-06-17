<script setup lang="ts">
// BottomNav — the primary-navigation pill, relocated to the bottom edge
// on phones (xs) so the four destinations sit within thumb reach. AppNav
// drops its centre pill on xs in turn (see AppNav.vue).
//
// This is the SAME RSliderBtnGroup tab pill the top nav uses — same glass
// surface, same border, same sliding active indicator — just pinned to
// the bottom and stretched full-width. No bespoke nav surface and no
// alternate layout, so the brand look and feel stay identical top vs
// bottom. Routing and universal input (keyboard / gamepad roving,
// modality-gated focus rings) come from the primitive unchanged.
//
// Shown on `sm-and-down` (phones + small tablets / landscape), where the
// top nav drops its centre pill. Mount-gated on the breakpoint ref (not
// `display: none`) so the four router-links never sit hidden-but-focusable
// in the tab order on larger viewports.
import { RSliderBtnGroup } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useNavDestinations } from "@/v2/composables/useNavDestinations";

const { t } = useI18n();
const { smAndDown } = useBreakpoint();
const { destinations, activeId } = useNavDestinations();
</script>

<template>
  <div v-if="smAndDown" class="r-v2-bottom-nav">
    <RSliderBtnGroup
      :model-value="activeId"
      :items="destinations"
      variant="tab"
      class="r-v2-bottom-nav__group"
      :aria-label="t('common.primary-navigation')"
    />
  </div>
</template>

<style scoped>
/* Fixed bottom strip that just hosts the pill. Transparent — the pill
   itself carries the glass surface (tab variant), so it reads as a
   floating control matching the top nav. Side gutters follow the
   responsive `--r-row-pad`; the safe-area inset keeps the pill above a
   notched phone's home indicator. `pointer-events: none` on the strip +
   `auto` on the pill so taps in the transparent gutters fall through. */
.r-v2-bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  justify-content: center;
  padding: 8px var(--r-row-pad) calc(8px + env(safe-area-inset-bottom));
  pointer-events: none;
}

/* Fill the strip width reliably (an inline-flex element ignores
   `width: 100%` in some flex contexts; `flex: 1` doesn't). border-box so
   the pill's own padding + border stay inside that width. */
.r-v2-bottom-nav__group {
  pointer-events: auto;
  flex: 1;
  box-sizing: border-box;
  /* Cap the pill on large tablets so it stays thumb-sized; the strip's
     `justify-content: center` keeps it centred once capped. */
  max-width: var(--r-bottom-nav-max-w);
}

/* Each destination stretches to an equal quarter of the pill so the
   active indicator spans its full cell and reaches close to the pill's
   rounded background edges — and keeps doing so as the viewport widens,
   instead of leaving the items bunched in the centre. The indicator sits
   inside the pill's 4px padding, so even with sub-pixel cell rounding it
   never grazes the border. */
.r-v2-bottom-nav__group :deep(.r-slider-btn-group__btn) {
  flex: 1;
  justify-content: center;
}

/* Icon-only on phones — four full-width inline labels won't fit, and the
   icon-only treatment matches the top-nav-on-xs precedent. The
   router-link `aria-label` (set by RSliderBtnGroup from each item's
   `ariaLabel`) stays the source of accessible naming. */
.r-v2-bottom-nav__group :deep(.r-slider-btn-group__label) {
  display: none;
}
</style>
