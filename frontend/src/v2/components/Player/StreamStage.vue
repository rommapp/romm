<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

// The surface a streaming session renders into: the container's iframe, the
// auto-hiding control bar over it, and the focus handling the emulator needs
// to see a gamepad. The bar's contents are the caller's, which is the only
// thing the game player and the admin desktop disagree about.
const props = withDefaults(
  defineProps<{
    /** The container URL to render. Empty until a session is claimed. */
    src: string;
    frameTitle: string;
    /** Whether a session is live. Focus is only forced while it is. */
    active?: boolean;
  }>(),
  { active: true },
);

const stageRef = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);
const isUIVisible = ref(true);
const isFullscreen = ref(false);

let uiTimeout: ReturnType<typeof setTimeout> | null = null;
let attachTimeouts: ReturnType<typeof setTimeout>[] = [];
let iframeLoadCleanup: (() => void) | null = null;
let contentWindowCleanup: (() => void) | null = null;

function showUI(): void {
  isUIVisible.value = true;
  if (uiTimeout) clearTimeout(uiTimeout);
  uiTimeout = setTimeout(() => {
    isUIVisible.value = false;
    focusStream();
  }, 2500);
}

// Browsers only deliver gamepad input to the focused frame, so the Selkies
// iframe must hold focus for the emulator to see the controller. Called on
// session start, iframe load, and whenever the control bar hides (returning
// focus taken by a toolbar click).
function focusStream(): void {
  if (!props.active) return;
  streamFrame.value?.focus();
}

function handleMouseMove(): void {
  showUI();
}

// Attach pointer listeners inside the iframe when same-origin, so the
// control bar reappears while the pointer is over the stream. Cross-
// origin containers fall back to the bottom hover sensor.
function attachIframeListeners(): void {
  const frame = streamFrame.value;
  if (!frame) return;

  iframeLoadCleanup?.();
  iframeLoadCleanup = null;

  const tryAttach = (): void => {
    focusStream();
    if (contentWindowCleanup) return;
    try {
      if (frame.contentWindow) {
        frame.contentWindow.addEventListener("mousemove", handleMouseMove);
        frame.contentWindow.addEventListener("mousedown", handleMouseMove);
        frame.contentWindow.addEventListener("touchstart", handleMouseMove);
        contentWindowCleanup = () => {
          try {
            frame.contentWindow?.removeEventListener(
              "mousemove",
              handleMouseMove,
            );
            frame.contentWindow?.removeEventListener(
              "mousedown",
              handleMouseMove,
            );
            frame.contentWindow?.removeEventListener(
              "touchstart",
              handleMouseMove,
            );
          } catch {
            // Cross-origin: listeners were never added, nothing to remove.
          }
        };
      }
    } catch {
      // Cross-origin container, can't access contentWindow.
    }
  };

  frame.addEventListener("load", tryAttach);
  iframeLoadCleanup = () => frame.removeEventListener("load", tryAttach);
  tryAttach();
}

function clearAttachTimeouts(): void {
  attachTimeouts.forEach((id) => clearTimeout(id));
  attachTimeouts = [];
}

watch(
  () => props.src,
  (src) => {
    clearAttachTimeouts();
    if (!src) return;
    showUI();
    attachTimeouts.push(setTimeout(attachIframeListeners, 100));
    // Some frames are slow to initialize their window; try again later.
    attachTimeouts.push(setTimeout(attachIframeListeners, 500));
  },
  { immediate: true },
);

// ── Fullscreen ─────────────────────────────────────────────────────
async function enterFullscreen(): Promise<void> {
  try {
    await stageRef.value?.requestFullscreen();
  } catch {
    // Fullscreen denied (permissions policy / gesture requirement).
  }
}

// Drop out of fullscreen before showing anything teleported to <body>: a
// fullscreened element paints over the whole page, dialogs included.
async function leaveFullscreen(): Promise<void> {
  if (!document.fullscreenElement) return;
  try {
    await document.exitFullscreen();
  } catch (error) {
    // Worst case the dialog opens behind fullscreen, so this is not fatal, but
    // it is invisible from the UI and worth surfacing to anyone debugging it.
    console.warn("Failed to exit fullscreen", error);
  }
}

async function toggleFullscreen(): Promise<void> {
  if (document.fullscreenElement) await leaveFullscreen();
  else await enterFullscreen();
}

function onFullscreenChange(): void {
  isFullscreen.value = !!document.fullscreenElement;
}
onMounted(() => {
  document.addEventListener("fullscreenchange", onFullscreenChange);
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  if (uiTimeout) clearTimeout(uiTimeout);
  clearAttachTimeouts();
  iframeLoadCleanup?.();
  contentWindowCleanup?.();
});

defineExpose({
  isUIVisible,
  isFullscreen,
  showUI,
  focusStream,
  enterFullscreen,
  leaveFullscreen,
  toggleFullscreen,
});
</script>

<template>
  <div
    ref="stageRef"
    class="r-v2-stage"
    :class="{ 'r-v2-stage--hide-cursor': !isUIVisible }"
    role="presentation"
    @mousemove="handleMouseMove"
  >
    <iframe
      v-if="src"
      ref="streamFrame"
      :src="src"
      class="r-v2-stage__frame"
      allow="gamepad *; fullscreen *; autoplay *"
      allowfullscreen
      referrerpolicy="no-referrer"
      :title="frameTitle"
    />

    <!-- Hover sensor for cross-origin fallback: bottom only so the top
         of the stream is not blocked by an invisible trigger zone. -->
    <div class="r-v2-stage__sensor" @mousemove="handleMouseMove" />

    <div
      class="r-v2-stage__bar"
      :class="{ 'r-v2-stage__bar--visible': isUIVisible }"
    >
      <slot
        name="bar"
        :is-fullscreen="isFullscreen"
        :toggle-fullscreen="toggleFullscreen"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-stage {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}
.r-v2-stage:fullscreen {
  inset: 0;
}
.r-v2-stage--hide-cursor {
  cursor: none;
}

.r-v2-stage__frame {
  width: 100%;
  height: 100%;
  border: none;
  background: var(--r-color-canvas-bg-deep);
  display: block;
}

.r-v2-stage__sensor {
  position: absolute;
  left: 0;
  bottom: 0;
  width: 100%;
  height: 80px;
  z-index: 5;
  background: transparent;
}

/* Control bar: glass strip pinned to the bottom of the stage.
   Visibility toggles via opacity so the stream never reflows. */
.r-v2-stage__bar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  min-height: 52px;
  background: color-mix(in srgb, var(--r-color-bg) 72%, transparent);
  border-top: 1px solid var(--r-color-border);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  z-index: 10;
  visibility: hidden;
  opacity: 0;
  transition:
    opacity 0.3s ease,
    visibility 0.3s ease;
  will-change: opacity;
}
.r-v2-stage__bar--visible {
  visibility: visible;
  opacity: 1;
}
</style>
