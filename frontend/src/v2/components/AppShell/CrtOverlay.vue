<script setup lang="ts">
// CrtOverlay — the persistent "CRT mode" shader. While CRT mode is on this
// sits above the whole app (teleported to <body> so it also covers
// teleported dialogs/menus), pointer-events:none so it never traps input,
// and layers scanlines + a rolling refresh band + vignette/curvature +
// flicker + an occasional chromatic-aberration glitch to sell the cathode-
// ray-tube look — without ever distorting the real DOM (it stays readable).
//
// Chrome-only: no stores/services/domain text. Self-gates on useCrtMode.
// The one-shot power-on flash is a separate component (CrtWarmup.vue).
import { useCrtMode } from "@/v2/composables/useCrtMode";

const { enabled } = useCrtMode();
</script>

<template>
  <Teleport to="body">
    <div v-if="enabled" class="r-crtfx" aria-hidden="true">
      <div class="r-crtfx__scan"></div>
      <div class="r-crtfx__roll"></div>
      <div class="r-crtfx__glitch"></div>
      <div class="r-crtfx__vignette"></div>
    </div>
  </Teleport>
</template>

<style scoped>
.r-crtfx {
  position: fixed;
  inset: 0;
  z-index: 99990;
  pointer-events: none;
  overflow: hidden;
  /* Phosphor "punch" — grade the live app behind the overlay (saturation +
     contrast). Done via backdrop-filter rather than a CSS `filter` on a
     layout container: this layer is teleported to <body>, a sibling of the
     app root, so it never becomes a containing block for the app's own
     position:fixed chrome (navbar, gallery SelectionBar, …). */
  backdrop-filter: saturate(1.3) contrast(1.05) brightness(1.02);
  /* Subtle whole-screen flicker — the CRT never sits perfectly still. */
  animation: r-crtfx-flicker 0.14s steps(2, end) infinite;
}

.r-crtfx__scan,
.r-crtfx__roll,
.r-crtfx__glitch,
.r-crtfx__vignette {
  position: absolute;
  inset: 0;
}

/* Horizontal scanlines, drifting slowly upward so the grille feels alive. */
.r-crtfx__scan {
  background: repeating-linear-gradient(
    to bottom,
    color-mix(in srgb, black 34%, transparent) 0,
    color-mix(in srgb, black 34%, transparent) 1px,
    transparent 1px,
    transparent 3px
  );
  animation: r-crtfx-scan-roll 8s linear infinite;
}

/* Bright "vertical retrace" band sweeping down the screen. */
.r-crtfx__roll {
  background: linear-gradient(
    to bottom,
    transparent 0%,
    color-mix(in srgb, white 7%, transparent) 46%,
    color-mix(in srgb, var(--r-color-crt-glow) 9%, transparent) 50%,
    transparent 54%,
    transparent 100%
  );
  animation: r-crtfx-roll 7s linear infinite;
}

/* Chromatic-aberration ghost slices — idle most of the time, then jolt.
   Two stacked box-shadows give a red/cyan RGB-split fringe; the keyframes
   nudge the layer sideways in quick steps for the "tracking error" glitch. */
.r-crtfx__glitch {
  box-shadow:
    inset 2px 0 0
      color-mix(in srgb, var(--r-color-crt-ghost-warm) 22%, transparent),
    inset -2px 0 0
      color-mix(in srgb, var(--r-color-crt-ghost-cool) 22%, transparent);
  opacity: 0;
  animation: r-crtfx-glitch 6.5s steps(1, end) infinite;
}

/* Rounded-tube vignette + a faint inner curvature highlight. */
.r-crtfx__vignette {
  background: radial-gradient(
    ellipse at center,
    transparent 55%,
    color-mix(in srgb, black 55%, transparent) 100%
  );
  box-shadow:
    inset 0 0 120px color-mix(in srgb, black 45%, transparent),
    inset 0 0 30px color-mix(in srgb, var(--r-color-crt-glow) 6%, transparent);
}

@keyframes r-crtfx-flicker {
  0% {
    opacity: 0.94;
  }
  100% {
    opacity: 1;
  }
}

@keyframes r-crtfx-scan-roll {
  0% {
    background-position-y: 0;
  }
  100% {
    background-position-y: -120px;
  }
}

@keyframes r-crtfx-roll {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(100%);
  }
}

/* Mostly invisible; brief chromatic jolts at a few points in the loop. */
@keyframes r-crtfx-glitch {
  0%,
  11.5%,
  12.5%,
  46%,
  47.2%,
  72%,
  72.8%,
  100% {
    opacity: 0;
    transform: translateX(0);
  }
  12% {
    opacity: 0.9;
    transform: translateX(-3px);
  }
  46.6% {
    opacity: 0.7;
    transform: translateX(2px);
  }
  72.4% {
    opacity: 0.85;
    transform: translateX(-2px);
  }
}

/* Reduced motion: keep the static CRT texture (scanlines + vignette) but
   drop every moving / flickering layer. */
@media (prefers-reduced-motion: reduce) {
  .r-crtfx,
  .r-crtfx__scan {
    animation: none;
  }
  .r-crtfx__roll,
  .r-crtfx__glitch {
    display: none;
  }
}
</style>
