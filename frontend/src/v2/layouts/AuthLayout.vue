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
    <div class="r-v2-auth__lang">
      <LanguageSelector />
    </div>
    <VersionTag class="r-v2-auth__version" />
  </div>
</template>

<style scoped>
.r-v2-auth {
  position: relative;
  min-height: 100vh;
  display: grid;
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

.r-v2-auth__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  display: flex;
  justify-content: center;
}

.r-v2-auth__lang {
  position: absolute;
  left: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}

.r-v2-auth__version {
  position: absolute;
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
  /* Sits directly on the background art with no card behind it, so a soft
     black shadow keeps it legible over the lighter patches. */
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
}

/* Phones: shrink the stage gutter so the card claims nearly the full width
   (the cards cap themselves and clip internally via their own overflow). */
html[data-bp~="xs"] .r-v2-auth {
  padding: var(--r-space-3);
}
</style>
