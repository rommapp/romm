<script setup lang="ts">
// CrtWarmup — a purely cosmetic "CRT phosphor warm-up" easter egg, fired when
// CRT mode is switched ON (see useCrtMode / AppNav). Plays a fast, glitchy,
// old-television power-on flash: instant black-out, a bright collapsing
// scanline, a phosphor bloom with chromatic-aberration tearing, a sync-roll
// band and jittering scanlines, then a quick settle back to the live app.
//
// Chrome-only — no stores/services/domain, no user-visible text (so it stays
// trivially theme-agnostic). Teleported to <body> so it covers teleported
// overlays too, and rendered pointer-events:none so it never traps input.
// Auto-removes when the master timeline ends. Honours prefers-reduced-motion
// (a brief motion-free fade).
import { nextTick, ref } from "vue";

const visible = ref(false);
// Bumping the key remounts the layer so the CSS animations restart from
// frame 0 — lets the user re-trigger the gimmick mid-flash.
const runId = ref(0);

async function play() {
  visible.value = false;
  await nextTick();
  runId.value += 1;
  visible.value = true;
}

// `.self` so only the container's own master animation ends the run — child
// layer animations bubble their animationend but must not cut the timeline
// short. The master animation is the longest, so it fires last.
function onEnded() {
  visible.value = false;
}

defineExpose({ play });
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      :key="runId"
      class="r-crt"
      aria-hidden="true"
      @animationend.self="onEnded"
    >
      <div class="r-crt__bloom"></div>
      <div class="r-crt__line"></div>
      <div class="r-crt__glitch"></div>
      <div class="r-crt__roll"></div>
      <div class="r-crt__scan"></div>
      <div class="r-crt__vignette"></div>
    </div>
  </Teleport>
</template>

<style scoped>
.r-crt {
  position: fixed;
  inset: 0;
  z-index: 99999;
  pointer-events: none;
  overflow: hidden;
  background-color: var(--r-color-canvas-bg);
  animation: r-crt-master 1.05s linear both;
}

/* Each decorative layer shares the master duration so they all settle on the
   same frame; their keyframes place the action along the shared timeline. */
.r-crt__bloom,
.r-crt__line,
.r-crt__glitch,
.r-crt__roll,
.r-crt__scan,
.r-crt__vignette {
  position: absolute;
  inset: 0;
  animation-duration: 1.05s;
  animation-fill-mode: both;
}

/* White-hot core fading out to phosphor green — the main "flash". */
.r-crt__bloom {
  background: radial-gradient(
    ellipse at center,
    white 0%,
    color-mix(in srgb, var(--r-color-crt-glow) 85%, white) 16%,
    color-mix(in srgb, var(--r-color-crt-glow) 65%, transparent) 44%,
    transparent 72%
  );
  animation-name: r-crt-bloom;
  animation-timing-function: ease-out;
}

/* The iconic collapsing scanline that snaps in before the bloom blooms. */
.r-crt__line {
  top: 50%;
  bottom: auto;
  height: 3px;
  background: white;
  box-shadow:
    0 0 12px 4px white,
    0 0 40px 12px var(--r-color-crt-glow);
  transform: translateY(-50%) scaleY(1);
  animation-name: r-crt-line;
  animation-timing-function: ease-in;
}

/* Chromatic-aberration tearing — red/cyan RGB-split fringes that jump
   sideways in hard steps while the tube "locks on". */
.r-crt__glitch {
  box-shadow:
    inset 5px 0 0
      color-mix(in srgb, var(--r-color-crt-ghost-warm) 55%, transparent),
    inset -5px 0 0
      color-mix(in srgb, var(--r-color-crt-ghost-cool) 55%, transparent);
  opacity: 0;
  animation-name: r-crt-glitch;
  animation-timing-function: steps(1, end);
}

/* Bright vertical-hold "roll" band sweeping down before the picture settles. */
.r-crt__roll {
  background: linear-gradient(
    to bottom,
    transparent 0%,
    color-mix(in srgb, white 22%, transparent) 48%,
    color-mix(in srgb, var(--r-color-crt-glow) 20%, transparent) 52%,
    transparent 56%,
    transparent 100%
  );
  animation-name: r-crt-roll;
  animation-timing-function: linear;
}

.r-crt__scan {
  background: repeating-linear-gradient(
    to bottom,
    color-mix(in srgb, black 46%, transparent) 0,
    color-mix(in srgb, black 46%, transparent) 1px,
    transparent 1px,
    transparent 3px
  );
  animation-name: r-crt-scan;
  animation-timing-function: linear;
}

.r-crt__vignette {
  background: radial-gradient(
    ellipse at center,
    transparent 52%,
    color-mix(in srgb, black 70%, transparent) 100%
  );
  animation-name: r-crt-vignette;
  animation-timing-function: ease-out;
}

@keyframes r-crt-master {
  0% {
    background-color: transparent;
  }
  4% {
    background-color: var(--r-color-canvas-bg);
  }
  74% {
    background-color: var(--r-color-canvas-bg);
  }
  100% {
    background-color: transparent;
  }
}

@keyframes r-crt-line {
  0% {
    opacity: 0;
    transform: translateY(-50%) scaleY(0.3);
  }
  5% {
    opacity: 1;
    transform: translateY(-50%) scaleY(1);
  }
  16% {
    opacity: 1;
    transform: translateY(-50%) scaleY(1);
  }
  30% {
    opacity: 0.9;
    transform: translateY(-50%) scaleY(280);
  }
  40% {
    opacity: 0;
    transform: translateY(-50%) scaleY(340);
  }
  100% {
    opacity: 0;
  }
}

@keyframes r-crt-bloom {
  0%,
  13% {
    opacity: 0;
    transform: scale(0.7);
  }
  26% {
    opacity: 1;
    transform: scale(1.05);
  }
  46% {
    opacity: 0.4;
    transform: scale(1);
  }
  100% {
    opacity: 0;
    transform: scale(1);
  }
}

/* Hard-stepped chromatic tearing concentrated in the lock-on phase. */
@keyframes r-crt-glitch {
  0%,
  17%,
  20%,
  29%,
  35%,
  55%,
  100% {
    opacity: 0;
    transform: translateX(0);
  }
  18% {
    opacity: 1;
    transform: translateX(-8px);
  }
  24% {
    opacity: 1;
    transform: translateX(7px);
  }
  31% {
    opacity: 0.9;
    transform: translateX(-5px);
  }
  44% {
    opacity: 0.7;
    transform: translateX(4px);
  }
}

@keyframes r-crt-roll {
  0%,
  18% {
    transform: translateY(-120%);
    opacity: 0;
  }
  20% {
    opacity: 1;
  }
  70% {
    opacity: 1;
  }
  82%,
  100% {
    transform: translateY(120%);
    opacity: 0;
  }
}

@keyframes r-crt-scan {
  0%,
  20% {
    opacity: 0;
  }
  34% {
    opacity: 0.6;
  }
  80% {
    opacity: 0.25;
  }
  100% {
    opacity: 0;
  }
}

@keyframes r-crt-vignette {
  0%,
  14% {
    opacity: 0;
  }
  36% {
    opacity: 1;
  }
  100% {
    opacity: 0;
  }
}

/* Reduced motion: drop the busy sweeping / tearing layers, keep a brief
   phosphor-tinted fade so the easter egg still acknowledges the toggle. */
@media (prefers-reduced-motion: reduce) {
  .r-crt {
    animation: r-crt-reduced 0.45s ease-out both;
  }
  .r-crt__line,
  .r-crt__glitch,
  .r-crt__roll,
  .r-crt__scan,
  .r-crt__vignette {
    display: none;
  }
  .r-crt__bloom {
    animation: r-crt-reduced-bloom 0.45s ease-out both;
  }
  @keyframes r-crt-reduced {
    0% {
      background-color: var(--r-color-canvas-bg);
    }
    100% {
      background-color: transparent;
    }
  }
  @keyframes r-crt-reduced-bloom {
    0% {
      opacity: 0.6;
    }
    100% {
      opacity: 0;
    }
  }
}
</style>
