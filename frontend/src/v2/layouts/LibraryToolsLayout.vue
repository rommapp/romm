<script setup lang="ts">
// LibraryToolsLayout — sub-layout shared by every Library Tools route
// (Scan / Upload / Patcher). The chrome it owns is minimal: a slot
// for view-specific CTAs (teleport target) and a conditionally-styled
// container around the `<router-view name="v2" />`.
//
// The tool picker that used to live here moved to AppNav as a sub-pill
// that drops down from the Library Tools tab. Keeping a second pill
// inside the layout was redundant — AppNav is the source of truth for
// "which tool is active", and the layout's job is just to host the
// active tool's output.
//
// `bare` is route-level (`meta: { bare: true }`) — Scan and Patcher
// use it because they own their own surfaces and don't want the
// outer glass panel double-nesting under them. Upload doesn't set
// it, so it gets the default panel.
//
// `#r-v2-lt-actions` is a teleport target in the header: a view can
// drop a CTA via `<Teleport to="#r-v2-lt-actions" defer>`. The `defer`
// modifier is mandatory when the teleport source is a child of this
// layout — without it, the target isn't in the DOM yet on initial
// mount (children render before parents insert) and the Teleport
// vnode corrupts, crashing on the next unmount.
import { computed } from "vue";
import { useRoute } from "vue-router";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";

defineOptions({ inheritAttrs: false });

const route = useRoute();

const isBare = computed(() => route.meta?.bare === true);

// Library Tools pages share the current cover-art background from
// wherever the user came from — same no-op pattern as SettingsLayout.
const setBgArt = useBackgroundArt();
setBgArt(null);
</script>

<template>
  <section class="r-v2-lt">
    <!-- View-specific CTA slot. The header row collapses to nothing
         when no view teleports into it (`:empty` rule below). -->
    <header class="r-v2-lt__head">
      <div id="r-v2-lt-actions" class="r-v2-lt__actions" />
    </header>

    <!-- Single router-view with a conditional wrapper class. The
         alternative (v-if / v-else with two router-views inside)
         confuses vue-router during the route transition — the
         outgoing branch unmounts before the incoming route's view
         binds, and the new content never paints. One router-view +
         class swap keeps the same component instance receiving the
         route update. -->
    <div :class="isBare ? 'r-v2-lt__bare' : 'r-v2-lt__panel'">
      <router-view name="v2" />
    </div>
  </section>
</template>

<style scoped>
/* Top padding clears the AppNav sub-pill (the Library Tools secondary
   pill that hangs from the navbar). The sub-pill is ~40px tall +
   8px gap + a bit of breathing room → 60px. The pill is always
   shown on Library Tools routes (and this layout only mounts on
   those routes), so the relationship is deterministic. */
.r-v2-lt {
  width: 100%;
  max-width: var(--r-page-max-w);
  margin: 0 auto;
  padding: 60px 40px 60px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* The head row only renders content when a view teleports into it.
   Empty → collapse the row entirely so we don't get a phantom gap
   above the panel. */
.r-v2-lt__head {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 18px;
  flex-wrap: wrap;
  min-height: 0;
}
.r-v2-lt__head:has(.r-v2-lt__actions:empty) {
  display: none;
}
.r-v2-lt__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 0;
}
.r-v2-lt__actions:empty {
  display: none;
}

.r-v2-lt__panel {
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  padding: 22px;
  min-height: 320px;
}

/* Bare variant — the view owns its own surfaces. Stack vertically
   so consumers can drop multiple cards/panels without each one
   needing its own flex wrapper. */
.r-v2-lt__bare {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 320px;
}

html[data-bp~="sm-and-down"] .r-v2-lt {
  padding: 56px var(--r-row-pad) 48px;
  gap: 14px;
}
</style>
