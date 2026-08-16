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

// How close to the top the pointer has to get before the bar appears. The bar
// lives at the top because the container's own taskbar and its reveal handle
// both sit on the bottom edge, where nothing of ours can share the space. Kept
// to a sliver so the emulator window's own title bar, which sits just below the
// top edge, still takes the pointer and stays draggable.
const BAR_REVEAL_BAND_PX = 6;

// Capture, because the stream's own input handling stops mousemove from
// bubbling over the parts of the page it claims, and passive so listening in
// on it can never delay that handling.
const FRAME_LISTENER_OPTS = { capture: true, passive: true } as const;

const hotEdgeHeight = `${BAR_REVEAL_BAND_PX}px`;

const stageRef = ref<HTMLElement | null>(null);
const streamFrame = ref<HTMLIFrameElement | null>(null);
const isUIVisible = ref(true);
const isFullscreen = ref(false);
// Whether the frame let us listen inside it. A cross-origin container never
// reports its pointer, so it gets the edge strip instead.
const sameOrigin = ref(false);
// The origin a room page announced from, empty until it does.
const roomOrigin = ref("");

let uiTimeout: ReturnType<typeof setTimeout> | null = null;
let attachTimeouts: ReturnType<typeof setTimeout>[] = [];
let frameCleanups: (() => void)[] = [];

function showUI(): void {
  isUIVisible.value = true;
  if (uiTimeout) clearTimeout(uiTimeout);
  uiTimeout = setTimeout(() => {
    isUIVisible.value = false;
    reclaimStreamFocus();
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

// The hide timer runs regardless of what is on screen, and a dialog over the
// stream holds focus on purpose: pulling it into the iframe there would take
// the keyboard away from the buttons the user is answering with.
function reclaimStreamFocus(): void {
  const focused = document.activeElement;
  const heldOutside =
    focused !== null &&
    focused !== document.body &&
    focused !== document.documentElement &&
    !(stageRef.value?.contains(focused) ?? false);
  if (heldOutside) return;
  focusStream();
}

function revealNearTop(offsetY: number): void {
  if (offsetY > BAR_REVEAL_BAND_PX) return;
  showUI();
}

function handleStageMouseMove(event: MouseEvent): void {
  const rect = stageRef.value?.getBoundingClientRect();
  if (!rect) return;
  revealNearTop(event.clientY - rect.top);
}

// Coordinates are measured against the viewport of whichever document the
// pointer is actually in, which is not always the stage frame: the container
// nests the stream inside a page of its own.
function handleFrameMouseMove(event: MouseEvent): void {
  revealNearTop(event.clientY);
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

// The container's own client applies volume and mute to the gain node in front
// of its audio output, and it drops any message whose origin is not its own.
// Same origin is what makes that reachable, so the bar can move this viewer's
// gain instead of asking the broker to move the whole container's mixer.
//
// A room page announces itself instead, and relays what we send on to the
// stream nested inside it. That is the only way across an origin boundary, and
// it is what a container served from its own host does. Containers that say
// nothing are left to the broker fallback, which is all they ever had.
// Returns whether there was anything to post to.
function postToStream(message: unknown): boolean {
  const frames = sameOriginFrames(streamFrame.value?.contentWindow ?? null);
  frames.forEach((win) => win.postMessage(message, window.location.origin));
  if (frames.length > 0) return true;
  const room = streamFrame.value?.contentWindow;
  if (!room || !roomOrigin.value) return false;
  room.postMessage(message, roomOrigin.value);
  return true;
}

// Set by the room's own announcement, so it is the frame's real origin rather
// than one parsed off a src that may have redirected.
function onFrameAnnounce(event: MessageEvent): void {
  if (event.source !== streamFrame.value?.contentWindow) return;
  if ((event.data as { type?: string } | null)?.type !== "roomReady") return;
  roomOrigin.value = event.origin;
}

function detachFrameListeners(): void {
  frameCleanups.forEach((off) => off());
  frameCleanups = [];
}

// Listen in every frame, so the top edge of the stream itself raises the bar
// wherever the pointer happens to be. Cross-origin containers report nothing
// and fall back to the edge strip.
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
    roomOrigin.value = "";
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
  window.addEventListener("message", onFrameAnnounce);
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  window.removeEventListener("message", onFrameAnnounce);
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
  postToStream,
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
         reach the bar is a strip of our own across the top of the stage. -->
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
  top: 0;
  height: v-bind(hotEdgeHeight);
  z-index: 5;
  background: transparent;
}

/* Control bar: glass strip pinned to the top of the stage.
   Visibility toggles via opacity so the stream never reflows. */
.r-v2-stage__bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  min-height: 52px;
  background: color-mix(in srgb, var(--r-color-bg) 72%, transparent);
  border-bottom: 1px solid var(--r-color-border);
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
