<script setup lang="ts">
// AuthLayout — full-viewport blurred background with a centred card stage
// for the auth flows (Login / Register / ResetPassword / Setup). Bottom
// corners hold the LanguageSelector (left) and VersionTag (right).
import { onMounted } from "vue";
import LanguageSelector from "@/v2/components/shared/LanguageSelector.vue";
import VersionTag from "@/v2/components/shared/VersionTag.vue";
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
    <!-- Bottom bar: language selector pinned left, version tag right. A
         single row so the "one on each side" split holds at every width
         (absolute on desktop, in normal flow below the card on phones). -->
    <div class="r-v2-auth__footer">
      <div class="r-v2-auth__lang">
        <LanguageSelector />
      </div>
      <VersionTag class="r-v2-auth__version" />
    </div>
  </div>
</template>

<style scoped>
.r-v2-auth {
  position: relative;
  min-height: 100vh;
  display: grid;
  /* Bound the single track to the viewport — an `auto` track sizes to the
     card's max-content and, on a narrow phone, that pushes the centred card
     past the right edge (clipped by `overflow: hidden`). `minmax(0, 1fr)`
     never exceeds the container. */
  grid-template-columns: minmax(0, 1fr);
  place-items: center;
  padding: var(--r-space-6);
  overflow: hidden;

  /* The auth background and the AuthCard/Setup glass are always dark
     (--r-color-canvas-bg-deep) regardless of theme, so the light-mode
     foreground/border tokens (near-black) would be unreadable here. Force
     the dark-mode palette for everything inside the auth layout — the page
     text, the LanguageSelector, the VersionTag, and surface/border-driven
     bits like the RSteps connector lines and dots. CSS custom properties
     inherit into descendants, and the override is scoped to .r-v2-auth so
     those shared components stay theme-driven elsewhere. */
  --r-color-fg: #ffffff;
  --r-color-fg-secondary: rgba(255, 255, 255, 0.75);
  --r-color-fg-muted: rgba(255, 255, 255, 0.45);
  --r-color-fg-faint: rgba(255, 255, 255, 0.25);
  --r-color-surface: rgba(255, 255, 255, 0.07);
  --r-color-surface-hover: rgba(255, 255, 255, 0.12);
  --r-color-border: rgba(255, 255, 255, 0.07);
  --r-color-border-strong: rgba(255, 255, 255, 0.15);
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

/* Bottom bar — absolute full-width row on desktop: language selector hugs
   the left, version tag the right (space-between). */
.r-v2-auth__footer {
  position: absolute;
  left: var(--r-space-4);
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-3);
}

.r-v2-auth__version {
  /* Sits directly on the background art with no card behind it, so a soft
     black shadow keeps it legible over the lighter patches. */
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
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
     (chrome-hidden) viewport, which — once the address bar reappears — forces
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
