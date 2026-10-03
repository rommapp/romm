<script setup lang="ts">
// AuthLayout: full-viewport blurred background with a centred card stage
// for the auth flows (Login / Register / ResetPassword / Setup). Bottom
// bar is the shared AuthFooter.
import { onMounted } from "vue";
import NotificationHost from "@/v2/components/Notifications/NotificationHost.vue";
import AuthFooter from "@/v2/components/shared/AuthFooter.vue";
import { installBreakpointAttribute } from "@/v2/composables/useBreakpoint";
import { useInputModality } from "@/v2/composables/useInputModality";

// The auth / setup flow runs under THIS layout, not AppLayout, so it must
// install the same `<html>` mirrors. Without them no `data-bp` responsive
// rule and no modality-gated focus/hit-target style applies here (the setup
// wizard's columns wouldn't even collapse on a phone).
installBreakpointAttribute();
const { install: installInputModality } = useInputModality();
onMounted(installInputModality);
</script>

<template>
  <div class="r-v2-auth">
    <div class="r-v2-auth__bg" />
    <main class="r-v2-auth__stage">
      <router-view name="v2" />
    </main>
    <!-- Absolute on desktop, in normal flow below the card on phones. -->
    <AuthFooter class="r-v2-auth__footer" />
    <NotificationHost />
  </div>
</template>

<style scoped>
.r-v2-auth {
  position: relative;
  min-height: 100vh;
  display: grid;
  /* Bound the single track to the viewport: an `auto` track sizes to the
     card's max-content and, on a narrow phone, that pushes the centred card
     past the right edge (clipped by `overflow: hidden`). `minmax(0, 1fr)`
     never exceeds the container. */
  grid-template-columns: minmax(0, 1fr);
  place-items: center;
  padding: max(var(--r-space-6), env(safe-area-inset-top, 0px))
    max(var(--r-space-6), env(safe-area-inset-right, 0px))
    max(var(--r-space-6), env(safe-area-inset-bottom, 0px))
    max(var(--r-space-6), env(safe-area-inset-left, 0px));
  overflow: hidden;

  /* The auth background and the AuthCard/Setup glass are always dark
     (--r-color-canvas-bg-deep) regardless of theme, so the light-mode
     foreground/border tokens (near-black) would be unreadable here. Force
     the dark-mode palette for everything inside the auth layout: the page
     text, the LanguageSelector, the VersionTag, and surface/border-driven
     bits like the RSteps connector lines and dots. CSS custom properties
     inherit into descendants, and the override is scoped to .r-v2-auth so
     those shared components stay theme-driven elsewhere. */
  --r-color-fg: white;
  --r-color-fg-secondary: color-mix(in srgb, white 75%, transparent);
  --r-color-fg-muted: color-mix(in srgb, white 45%, transparent);
  --r-color-fg-faint: color-mix(in srgb, white 25%, transparent);
  --r-color-surface: color-mix(in srgb, white 7%, transparent);
  --r-color-surface-hover: color-mix(in srgb, white 12%, transparent);
  --r-color-border: color-mix(in srgb, white 7%, transparent);
  --r-color-border-strong: color-mix(in srgb, white 15%, transparent);
}

.r-v2-auth__bg {
  position: absolute;
  inset: 0;
  background-image: url("/assets/auth_background.svg");
  background-size: cover;
  background-position: center;
  z-index: 0;
}

/* Firefox: WebRender re-rasterizes the animated SVG every frame, pegging the
   GPU. Swap to the static variant in Gecko only (the empty `url-prefix()`
   hack matches all Firefox pages and stays enabled by default). */
@-moz-document url-prefix() {
  .r-v2-auth__bg {
    background-image: url("/assets/auth_background_static.svg");
  }
}

.r-v2-auth__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  display: flex;
  justify-content: center;
}

.r-v2-auth__footer {
  position: absolute;
  left: var(--r-space-4);
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}

/* Phones: lay the card and the bottom bar out in normal flow instead of
   centring a tall card over an absolutely-positioned bar (which overlapped on
   short screens). The stage fills the available height (the card scrolls
   internally) and the bar drops below it, keeping the language-left /
   version-right split. The smaller gutter lets the card claim the width. */
html[data-bp~="xs"] .r-v2-auth {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  /* Both height AND min-height in dvh so the layout tracks the mobile browser
     chrome as it shows/hides. The base `min-height: 100vh` uses the LARGE
     (chrome-hidden) viewport, which, once the address bar reappears, forces
     the layout taller than the visible area, pushing the bottom bar below the
     fold and requiring a page scroll. dvh is the dynamic viewport, so it
     shrinks with the bar and the card fills exactly the visible space. */
  height: 100dvh;
  min-height: 100dvh;
  padding: var(--r-space-3);
  gap: var(--r-space-3);
}
html[data-bp~="xs"] .r-v2-auth__stage {
  /* Bounded, non-scrolling (flex-basis 0 → available space, content-
     independent). The card fills it via `align-self: stretch` and scrolls
     its own lists region internally, desktop-style. Using a definite flex
     cross-size (not a `height: 100%` percentage) avoids the re-layout
     collapse. */
  flex: 1 1 0;
  min-height: 0;
  align-items: center;
}
html[data-bp~="xs"] .r-v2-auth__footer {
  position: static;
  flex: 0 0 auto;
}
</style>
