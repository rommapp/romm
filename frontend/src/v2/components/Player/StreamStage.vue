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

// How close to the bottom the pointer has to get before the bar appears. Deep
// enough that the bar is already up by the time the pointer reaches the screen
// edge, where the host OS keeps its own auto-hiding taskbar.
const BAR_REVEAL_BAND_PX = 84;

// The cross-origin fallback strip is an overlay: any pixel it covers is a pixel
// of the container below that cannot be clicked. So it stops short of the
// bottom edge, leaving the container's own taskbar reachable and keeping the
// band clear of the host taskbar's reveal edge.
const BAR_EDGE_GAP_PX = 36;

// The container keeps its own reveal handle at dead centre of the bottom edge,
// right under where our bar lands. Raising the bar there buries it, so a column
// this wide is left alone: the bar neither appears while the pointer is in it
// nor stays up once it gets there, which keeps the handle reachable. Wide
// enough to approach the handle from any angle without clipping the column.
const BAR_DEAD_SPOT_PX = 260;

// Capture, because the stream's own input handling stops mousemove from
// bubbling over the parts of the page it claims, and passive so listening in
// on it can never delay that handling.
const FRAME_LISTENER_OPTS = { capture: true, passive: true } as const;

const hotEdgeBottom = `${BAR_EDGE_GAP_PX}px`;
const hotEdgeHeight = `${BAR_REVEAL_BAND_PX - BAR_EDGE_GAP_PX}px`;

const stageRef = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);
const isUIVisible = ref(true);
const isFullscreen = ref(false);
// Whether the frame let us listen inside it. A cross-origin container never
// reports its pointer, so it gets the edge strip instead.
const sameOrigin = ref(false);

let uiTimeout: ReturnType<typeof setTimeout> | null = null;
let attachTimeouts: ReturnType<typeof setTimeout>[] = [];
let frameCleanups: (() => void)[] = [];

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

function revealNearBottom(
  offsetX: number,
  offsetY: number,
  width: number,
  height: number,
): void {
  if (height - offsetY > BAR_REVEAL_BAND_PX) return;
  if (width > 0 && Math.abs(offsetX - width / 2) <= BAR_DEAD_SPOT_PX / 2)
    return;
  showUI();
}

function handleStageMouseMove(event: MouseEvent): void {
  const rect = stageRef.value?.getBoundingClientRect();
  if (!rect) return;
  revealNearBottom(
    event.clientX - rect.left,
    event.clientY - rect.top,
    rect.width,
    rect.height,
  );
}

// Coordinates are measured against the viewport of whichever document the
// pointer is actually in, which is not always the stage frame: the container
// nests the stream inside a page of its own.
function handleFrameMouseMove(event: MouseEvent): void {
  const frame = streamFrame.value;
  const width = event.view?.innerWidth ?? frame?.clientWidth ?? 0;
  const height = event.view?.innerHeight ?? frame?.clientHeight ?? 0;
  revealNearBottom(event.clientX, event.clientY, width, height);
}

// Touch has no hover to track, and a tap is deliberate enough to mean it.
function handleTouchStart(): void {
  showUI();
}

// Every same-origin window in the tree under the stage frame. The container
// nests the stream inside a page of its own, and a pointer over one document
// is invisible to all the others, so each one has to be listened to directly.
function sameOriginFrames(win: Window | null, found: Window[] = []): Window[] {
  if (!win) return found;
  try {
    void win.document.readyState;
  } catch {
    // Cross-origin frame: it reports nothing and cannot be reached into.
    return found;
  }
  found.push(win);
  for (let i = 0; i < win.frames.length; i += 1) {
    sameOriginFrames(win.frames[i], found);
  }
  return found;
}

// Selkies paints the session into a 2D canvas it creates itself, falling back
// to a video element on the WebRTC path. Neither is tainted, so a same-origin
// container lets the frame be read straight out of the page. This is the only
// capture that cannot stall the emulator: asking it to grab its own framebuffer
// is what deadlocks a GPU-rendered core.
const STREAM_CANVAS_ID = "videoCanvas";
const STREAM_VIDEO_ID = "stream";
// Long edge of the captured image. It is a thumbnail, and a full-resolution
// PNG of the stream is several megabytes per save.
const CAPTURE_MAX_EDGE = 960;

function streamSurface(): HTMLCanvasElement | HTMLVideoElement | null {
  // Elements come from another frame's realm, where `instanceof` against this
  // document's constructors is always false, so match on the tag instead.
  for (const win of sameOriginFrames(
    streamFrame.value?.contentWindow ?? null,
  )) {
    const el = win.document.getElementById(STREAM_CANVAS_ID);
    if (el?.tagName === "CANVAS") {
      const canvas = el as HTMLCanvasElement;
      if (canvas.width > 0) return canvas;
    }
    const videoEl = win.document.getElementById(STREAM_VIDEO_ID);
    if (videoEl?.tagName === "VIDEO") {
      const video = videoEl as HTMLVideoElement;
      if (video.videoWidth > 0) return video;
    }
  }
  return null;
}

// PNG because that is what the states API stores and what the backend's
// thumbnail guard checks the magic bytes for.
async function captureFrame(): Promise<Blob | null> {
  const surface = streamSurface();
  if (!surface) return null;
  const isVideo = surface.tagName === "VIDEO";
  const video = surface as HTMLVideoElement;
  const canvas = surface as HTMLCanvasElement;
  const sw = isVideo ? video.videoWidth : canvas.width;
  const sh = isVideo ? video.videoHeight : canvas.height;
  if (!sw || !sh) return null;

  const scale = Math.min(1, CAPTURE_MAX_EDGE / Math.max(sw, sh));
  const out = document.createElement("canvas");
  out.width = Math.round(sw * scale);
  out.height = Math.round(sh * scale);
  const ctx = out.getContext("2d");
  if (!ctx) return null;
  try {
    ctx.drawImage(surface, 0, 0, out.width, out.height);
  } catch {
    // A surface mid-resize has no drawable frame yet.
    return null;
  }
  return new Promise((resolve) => out.toBlob(resolve, "image/png"));
}

function detachFrameListeners(): void {
  frameCleanups.forEach((off) => off());
  frameCleanups = [];
}

// Listen in every frame, so the bottom edge of the stream itself raises the
// bar wherever the pointer happens to be. Cross-origin containers report
// nothing and fall back to the edge strip.
//
// A full re-scan rather than a one-time attach: a frame that has navigated is
// a new document carrying none of our listeners, and the frame the container
// streams into starts life as about:blank.
function attachIframeListeners(): void {
  const frame = streamFrame.value;
  if (!frame) return;

  detachFrameListeners();
  focusStream();

  const frames = sameOriginFrames(frame.contentWindow);
  sameOrigin.value = frames.length > 0;

  frames.forEach((win) => {
    win.addEventListener(
      "mousemove",
      handleFrameMouseMove,
      FRAME_LISTENER_OPTS,
    );
    win.addEventListener("touchstart", handleTouchStart, FRAME_LISTENER_OPTS);
    frameCleanups.push(() => {
      try {
        win.removeEventListener(
          "mousemove",
          handleFrameMouseMove,
          FRAME_LISTENER_OPTS,
        );
        win.removeEventListener(
          "touchstart",
          handleTouchStart,
          FRAME_LISTENER_OPTS,
        );
      } catch {
        // The frame navigated away and took its listeners with it.
      }
    });

    win.document.querySelectorAll("iframe").forEach((nested) => {
      nested.addEventListener("load", attachIframeListeners);
      frameCleanups.push(() =>
        nested.removeEventListener("load", attachIframeListeners),
      );
    });
  });

  frame.addEventListener("load", attachIframeListeners);
  frameCleanups.push(() =>
    frame.removeEventListener("load", attachIframeListeners),
  );
}

function clearAttachTimeouts(): void {
  attachTimeouts.forEach((id) => clearTimeout(id));
  attachTimeouts = [];
}

watch(
  () => props.src,
  (src) => {
    clearAttachTimeouts();
    sameOrigin.value = false;
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
  detachFrameListeners();
});

defineExpose({
  isUIVisible,
  isFullscreen,
  showUI,
  focusStream,
  captureFrame,
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
    @mousemove="handleStageMouseMove"
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

    <!-- A cross-origin frame swallows the pointer, so there the only way to
         reach the bar is a strip of our own across the bottom of the stage. -->
    <div
      v-if="!sameOrigin"
      class="r-v2-stage__edge"
      @mousemove="handleStageMouseMove"
      @touchstart="handleTouchStart"
    />

    <div
      class="r-v2-stage__bar"
      :class="{ 'r-v2-stage__bar--visible': isUIVisible }"
      @mousemove="handleStageMouseMove"
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

.r-v2-stage__edge {
  position: absolute;
  left: 0;
  right: 0;
  bottom: v-bind(hotEdgeBottom);
  height: v-bind(hotEdgeHeight);
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
