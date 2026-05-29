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

defineOptions({ inheritAttrs: false });

const route = useRoute();
const isBare = computed(() => route.meta?.bare === true);

// Settings pages share the current cover-art background from wherever
// the user came from. We don't paint over it; just no-op so a stale
// platform/ROM cover doesn't bleed through.
const setBgArt = useBackgroundArt();
setBgArt(null);
</script>

<template>
  <section class="r-v2-settings">
    <SettingsSidebar class="r-v2-settings__sidebar" />

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
  -webkit-backdrop-filter: blur(18px);
  padding: 18px;
}

.r-v2-settings__body--bare {
  background: transparent;
  border: 0;
  border-radius: 0;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  padding: 0;
  gap: 14px;
}

html[data-bp~="sm-and-down"] .r-v2-settings {
  flex-direction: column;
}
html[data-bp~="sm-and-down"] .r-v2-settings__sidebar {
  width: 100%;
}
html[data-bp~="sm-and-down"] .r-v2-settings__content {
  padding: 24px var(--r-row-pad) 48px;
}
</style>
