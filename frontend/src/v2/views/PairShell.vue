<script setup lang="ts">
// PairShell: minimal AuthLayout-equivalent for /pair under v2. We can't
// reuse AuthLayout directly because /pair is a top-level route with no
// nested <router-view>; the shell inlines Pair.vue instead.
import AuthFooter from "@/v2/components/shared/AuthFooter.vue";
import Pair from "@/v2/views/Pair.vue";
</script>

<template>
  <div class="r-v2-pair-shell">
    <div class="r-v2-pair-shell__bg" />
    <main class="r-v2-pair-shell__stage">
      <Pair />
    </main>
    <AuthFooter class="r-v2-pair-shell__footer" />
  </div>
</template>

<style scoped>
.r-v2-pair-shell {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--r-space-6);
  overflow: hidden;

  /* The background and the Pair card are always dark, so pin text and
     borders to the always-light overlay tokens for v2-light. */
  --r-color-fg: var(--r-color-overlay-fg);
  --r-color-fg-secondary: var(--r-color-overlay-fg-secondary);
  --r-color-fg-muted: var(--r-color-overlay-fg-muted);
  --r-color-border: var(--r-color-overlay-border);
  --r-color-border-strong: var(--r-color-overlay-border-strong);
}

.r-v2-pair-shell__bg {
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
  .r-v2-pair-shell__bg {
    background-image: url("/assets/auth_background_static.svg");
  }
}

.r-v2-pair-shell__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
}

/* Absolute so it stays out of the grid and the stage keeps its centring. */
.r-v2-pair-shell__footer {
  position: absolute;
  left: var(--r-space-4);
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}
</style>
