<script setup lang="ts">
// SettingsLayout — sub-layout shared by every Settings route. Mounts
// the sidebar + content column and renders the active settings view
// via `<router-view name="v2" />`. Replaces the old
// `SettingsShell` wrapper-from-the-view pattern: the route tree owns
// the chrome now, the views just render their body.
//
// Layout: two columns sharing a vertical hairline divider. The
// sidebar is `position: sticky` so it follows the user as the document
// scrolls — a single document scrollbar drives both columns, matching
// Home's behaviour (no nested scroll containers). Bounded by
// `--r-page-max-w` so the layout never stretches beyond the same width
// budget GameDetails uses.
//
// `bare` is route-level: views that already provide their own section
// cards (Administration, ServerStats, …) set `meta: { bare: true }`
// on their route so the layout drops the outer glass panel and lets
// the embedded cards breathe instead of double-nesting.
import { computed } from "vue";
import { useRoute } from "vue-router";
import SettingsSidebar from "@/v2/components/Settings/SettingsSidebar.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";

defineOptions({ inheritAttrs: false });

const route = useRoute();
// On `sm-and-down` the sidebar is dropped entirely — the navbar UserMenu
// mirrors the same section IA, so a duplicate in-page strip is redundant on
// phones. Mount-gated (not display:none) so the hidden links never sit in
// the tab / spatial-nav order.
const { mdAndUp } = useBreakpoint();
const isBare = computed(() => route.meta?.bare === true);
// `fill` views (e.g. Logs) pin to the viewport height and scroll their own
// content internally instead of growing the document.
const isFill = computed(() => route.meta?.fill === true);

// Settings pages share the current cover-art background from wherever
// the user came from. We don't paint over it; just no-op so a stale
// platform/ROM cover doesn't bleed through.
const setBgArt = useBackgroundArt();
setBgArt(null);
</script>

<template>
  <section class="r-v2-settings" :class="{ 'r-v2-settings--fill': isFill }">
    <SettingsSidebar v-if="mdAndUp" class="r-v2-settings__sidebar" />

    <div class="r-v2-settings__content">
      <!-- Single router-view with a conditional wrapper class. Two
           router-views under v-if/v-else confuse vue-router during
           the transition — the outgoing branch unmounts before the
           new route's view binds, and content goes stale. One
           router-view + class swap keeps the same instance live. -->
      <div
        class="r-v2-settings__body"
        :class="{ 'r-v2-settings__body--bare': isBare }"
      >
        <router-view name="v2" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.r-v2-settings {
  display: flex;
  align-items: flex-start;
  min-height: calc(100vh - var(--r-nav-h));
  width: 100%;
  max-width: var(--r-page-max-w);
  margin: 0 auto;
}

.r-v2-settings__sidebar {
  width: 220px;
  flex-shrink: 0;
  /* Sticky + height owned entirely by SettingsSidebar (single-source
     of truth, no cross-scope cascade ambiguity). */
}

.r-v2-settings__content {
  flex: 1;
  min-width: 0;
  padding: 32px 40px 60px;
}

/* Default body = panel mode (background + border + padding). Bare
   views drop the panel chrome and stack their own section cards
   directly. The `.r-v2-settings__body` class is on the wrapper for
   both modes; the `--bare` modifier strips the panel surface. */
.r-v2-settings__body {
  display: flex;
  flex-direction: column;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  padding: 18px;
}

.r-v2-settings__body--bare {
  background: transparent;
  border: 0;
  border-radius: 0;
  backdrop-filter: none;
  padding: 0;
  gap: 14px;
}

/* Fill mode — the active view pins to the viewport height and owns its own
   internal scroll (the document itself doesn't scroll). The content column
   stretches to the section height; its body flex-fills so the view can grow
   to the bottom, leaving a clean margin equal to the in-view gutters. */
.r-v2-settings--fill {
  height: calc(100vh - var(--r-nav-h));
  height: calc(100dvh - var(--r-nav-h));
  /* The explicit height owns the sizing; without this the base
     `min-height: calc(100vh - nav)` (larger, and `vh` not `dvh`) wins and
     inflates the section past the viewport, forcing a document scroll. */
  min-height: 0;
}
/* On phones the fixed bottom tab bar overlays the viewport bottom. A fill
   view scrolls its own content internally, so it doesn't need to run under the
   bar — reserve the bar's height so the panel stops just above it (no content
   trapped behind the bar, no second document-level scroll). */
html[data-bp~="sm-and-down"] .r-v2-settings--fill {
  height: calc(
    100dvh - var(--r-nav-h) - var(--r-bottom-nav-h) -
      env(safe-area-inset-bottom)
  );
}
.r-v2-settings--fill .r-v2-settings__content {
  align-self: stretch;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding-bottom: 12px;
  overflow: hidden;
}
.r-v2-settings--fill .r-v2-settings__body {
  flex: 1;
  min-height: 0;
}

/* On sm-and-down the sidebar is unmounted (see script), so the content
   column fills the row on its own — just tighten the gutters to the
   responsive page padding. */
html[data-bp~="sm-and-down"] .r-v2-settings__content {
  padding: 24px var(--r-row-pad) 48px;
}
/* Fill views own their height and reserve the bottom bar separately, so the
   generous 48px scroll gutter above just leaves a big empty band under the
   panel — trim it to a small breather. */
html[data-bp~="sm-and-down"] .r-v2-settings--fill .r-v2-settings__content {
  padding-bottom: 12px;
}
</style>
