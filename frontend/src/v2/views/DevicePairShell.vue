<script setup lang="ts">
/**
 * DevicePairShell — minimal AuthLayout-equivalent for `/pair/device` under
 * v2. Mirrors {@link PairShell}: `/pair/device` is a top-level route with no
 * nested `<router-view>`, so the shell inlines {@link DevicePair} instead of
 * reusing AuthLayout directly.
 */
import LanguageSelector from "@/v2/components/shared/LanguageSelector.vue";
import VersionTag from "@/v2/components/shared/VersionTag.vue";
import DevicePair from "@/v2/views/DevicePair.vue";
</script>

<template>
  <div class="r-v2-devpair-shell">
    <div class="r-v2-devpair-shell__bg" />
    <main class="r-v2-devpair-shell__stage">
      <DevicePair />
    </main>
    <div class="r-v2-devpair-shell__lang">
      <LanguageSelector />
    </div>
    <VersionTag class="r-v2-devpair-shell__version" />
  </div>
</template>

<style scoped>
.r-v2-devpair-shell {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--r-space-6);
  overflow: hidden;

  /* The auth background and the glass card are always dark
     (--r-color-canvas-bg-deep) regardless of theme, so pin the foreground and
     borders to the always-light overlay tokens — the same fixed values that
     ride over cover art — so text stays legible in v2-light too. */
  --r-color-fg: var(--r-color-overlay-fg);
  --r-color-fg-secondary: var(--r-color-overlay-fg-secondary);
  --r-color-fg-muted: var(--r-color-overlay-fg-muted);
  --r-color-border: var(--r-color-overlay-border);
  --r-color-border-strong: var(--r-color-overlay-border-strong);
}

.r-v2-devpair-shell__bg {
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
  .r-v2-devpair-shell__bg {
    background-image: url("/assets/auth_background_static.svg");
  }
}

.r-v2-devpair-shell__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 460px;
}

.r-v2-devpair-shell__lang {
  position: absolute;
  left: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}

.r-v2-devpair-shell__version {
  position: absolute;
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}
</style>
