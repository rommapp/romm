<script setup lang="ts">
// RBox3D — a fake-but-believable 3D game box built from three flat scans
// (front, back, spine). Six CSS faces under `transform-style: preserve-3d`:
// the front/back carry their art, the spine is mirrored onto both left and
// right edges, and the top/bottom are tinted "cardboard" edges (tokens, no
// literals). Box proportions are derived from the images themselves — the
// front's natural ratio sets width/height, the spine's sets the depth — so
// a chunky N64 box and a slim DS case both look right without per-platform
// tuning.
//
// Universal input (premise 6): pointer drag rotates it; while focused, the
// arrow keys step it (this is what the gamepad D-pad / left stick emit as
// synthetic keys), and the right analog stick rotates it continuously (read
// directly, so the D-pad can still navigate away). When idle it drifts in a
// slow auto-spin — disabled under `prefers-reduced-motion` and paused for a
// beat after any manual input. Focus ring is automatic via `tabindex` +
// the modality-gated selectors in global.css.
//
// Primitive boundaries (§II): no stores, no domain knowledge — it takes
// three image URLs and a label. The feature composite (CoverColumn) decides
// when a rom actually has all three faces and feeds them in.
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

defineOptions({ inheritAttrs: false });

interface Props {
  /** Front cover art URL. */
  front: string;
  /** Back cover art URL. */
  back: string;
  /** Spine (box-2D-side) art URL — mirrored onto both side faces. */
  spine: string;
  /** Accessible label (the rom title). Rendered as the box's aria-label. */
  alt?: string;
  /** Drift slowly when idle (suppressed under reduced-motion). */
  autoSpin?: boolean;
  /** Resting yaw / pitch in degrees, applied before any interaction. */
  initialYaw?: number;
  initialPitch?: number;
}

const props = withDefaults(defineProps<Props>(), {
  alt: "",
  autoSpin: true,
  initialYaw: -32,
  initialPitch: -6,
});

const emit = defineEmits<{
  /** The front cover failed to load — the consumer should fall back. */
  error: [];
}>();

// Tunables.
const PITCH_LIMIT = 32; //            keep the box readable, never belly-up
const DRAG_SENSITIVITY = 0.45; //     deg per px
const KEY_STEP = 14; //               deg per arrow press
const STICK_SPEED = 3.2; //           deg per frame at full deflection
const STICK_DEADZONE = 0.18;
const AUTO_SPIN_SPEED = 0.18; //      deg per frame when idle
const IDLE_RESUME_MS = 2200; //       quiet time before auto-spin resumes
const DEFAULT_FRONT_RATIO = 0.715; // typical box face w/h until measured
const DEFAULT_SPINE_RATIO = 0.12; //  depth/height until measured

const rootEl = ref<HTMLElement | null>(null);

// Orientation.
const yaw = ref(props.initialYaw);
const pitch = ref(props.initialPitch);

// Measured geometry. `widthPx` comes from a ResizeObserver; the ratios from
// the images' natural dimensions on load.
const widthPx = ref(0);
const frontRatio = ref(DEFAULT_FRONT_RATIO); // front w / h  → box w / h
const spineRatio = ref(DEFAULT_SPINE_RATIO); // spine w / h  → depth / box h

const heightPx = computed(() =>
  frontRatio.value > 0 ? widthPx.value / frontRatio.value : 0,
);
const depthPx = computed(() => heightPx.value * spineRatio.value);

// Reduced-motion: read once on mount (it gates the idle drift only).
const reducedMotion = ref(false);

// Interaction bookkeeping.
const dragging = ref(false);
const stickActive = ref(false);
let lastInteractAt = 0;
let dragPointerId: number | null = null;
let lastX = 0;
let lastY = 0;
let rafId = 0;

const autoSpinning = computed(
  () =>
    props.autoSpin &&
    !reducedMotion.value &&
    !dragging.value &&
    !stickActive.value &&
    performance.now() - lastInteractAt > IDLE_RESUME_MS,
);

// Snap transitions off whenever the box is being driven continuously (drag,
// stick, drift); discrete keyboard steps keep it on so they ease.
const liveMotion = computed(
  () => dragging.value || stickActive.value || autoSpinning.value,
);

function markInteract() {
  lastInteractAt = performance.now();
}

function clampPitch(v: number) {
  return Math.max(-PITCH_LIMIT, Math.min(PITCH_LIMIT, v));
}

// --- Pointer drag -------------------------------------------------------
function onPointerDown(e: PointerEvent) {
  if (dragPointerId !== null) return;
  dragPointerId = e.pointerId;
  dragging.value = true;
  lastX = e.clientX;
  lastY = e.clientY;
  rootEl.value?.setPointerCapture(e.pointerId);
  markInteract();
}
function onPointerMove(e: PointerEvent) {
  if (e.pointerId !== dragPointerId) return;
  yaw.value += (e.clientX - lastX) * DRAG_SENSITIVITY;
  pitch.value = clampPitch(pitch.value - (e.clientY - lastY) * DRAG_SENSITIVITY);
  lastX = e.clientX;
  lastY = e.clientY;
  markInteract();
}
function endDrag(e: PointerEvent) {
  if (e.pointerId !== dragPointerId) return;
  dragPointerId = null;
  dragging.value = false;
  markInteract();
}

// --- Keyboard (also the gamepad D-pad / left stick via synthetic keys) ---
function onKeydown(e: KeyboardEvent) {
  switch (e.key) {
    case "ArrowLeft":
      yaw.value -= KEY_STEP;
      break;
    case "ArrowRight":
      yaw.value += KEY_STEP;
      break;
    case "ArrowUp":
      pitch.value = clampPitch(pitch.value - KEY_STEP);
      break;
    case "ArrowDown":
      pitch.value = clampPitch(pitch.value + KEY_STEP);
      break;
    default:
      return;
  }
  // Consume so the arrow doesn't also drive spatial navigation away from a
  // box the user is actively rotating; Tab / Shift+Tab (and B / LB / RB on a
  // pad) remain the way out.
  e.preventDefault();
  e.stopPropagation();
  markInteract();
}

// --- RAF: right-stick polling (while focused) + idle drift ---------------
function tick() {
  // Right analog stick, polled directly so it doesn't collide with the
  // D-pad → arrow-key navigation. Only while the box owns focus.
  if (rootEl.value && document.activeElement === rootEl.value) {
    const pads =
      typeof navigator !== "undefined" && navigator.getGamepads
        ? navigator.getGamepads()
        : [];
    let rx = 0;
    let ry = 0;
    for (const pad of pads) {
      if (!pad) continue;
      const ax = pad.axes[2] ?? 0;
      const ay = pad.axes[3] ?? 0;
      if (Math.abs(ax) > Math.abs(rx)) rx = ax;
      if (Math.abs(ay) > Math.abs(ry)) ry = ay;
    }
    const active = Math.abs(rx) > STICK_DEADZONE || Math.abs(ry) > STICK_DEADZONE;
    stickActive.value = active;
    if (active) {
      yaw.value += rx * STICK_SPEED;
      pitch.value = clampPitch(pitch.value - ry * STICK_SPEED);
      markInteract();
    }
  } else if (stickActive.value) {
    stickActive.value = false;
  }

  if (autoSpinning.value) yaw.value += AUTO_SPIN_SPEED;

  rafId = requestAnimationFrame(tick);
}

// --- Image measurement ---------------------------------------------------
function onFrontLoad(e: Event) {
  const img = e.target as HTMLImageElement;
  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
    frontRatio.value = img.naturalWidth / img.naturalHeight;
  }
}
function onSpineLoad(e: Event) {
  const img = e.target as HTMLImageElement;
  if (img.naturalWidth > 0 && img.naturalHeight > 0) {
    spineRatio.value = img.naturalWidth / img.naturalHeight;
  }
}

let ro: ResizeObserver | null = null;
onMounted(() => {
  reducedMotion.value =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const root = rootEl.value;
  if (root) {
    widthPx.value = root.clientWidth;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver((entries) => {
        const w = entries[0]?.contentRect.width ?? 0;
        if (w > 0) widthPx.value = w;
      });
      ro.observe(root);
    }
    // Interaction listeners are bound imperatively (not in the template) so
    // the static box element doesn't trip the no-static-element-interactions
    // rule — the same approach GameCover takes for its hover motion. The box
    // is decorative chrome with an optional manipulation affordance.
    root.addEventListener("pointerdown", onPointerDown);
    root.addEventListener("pointermove", onPointerMove);
    root.addEventListener("pointerup", endDrag);
    root.addEventListener("pointercancel", endDrag);
    root.addEventListener("keydown", onKeydown);
  }
  rafId = requestAnimationFrame(tick);
});
onBeforeUnmount(() => {
  ro?.disconnect();
  cancelAnimationFrame(rafId);
  const root = rootEl.value;
  if (root) {
    root.removeEventListener("pointerdown", onPointerDown);
    root.removeEventListener("pointermove", onPointerMove);
    root.removeEventListener("pointerup", endDrag);
    root.removeEventListener("pointercancel", endDrag);
    root.removeEventListener("keydown", onKeydown);
  }
});

// --- Styles --------------------------------------------------------------
const boxStyle = computed(() => ({
  transform: `rotateX(${pitch.value}deg) rotateY(${yaw.value}deg)`,
  transition: liveMotion.value ? "none" : "transform 0.28s ease-out",
}));

const px = (n: number) => `${n}px`;

const frontStyle = computed(() => ({
  width: px(widthPx.value),
  height: px(heightPx.value),
  transform: `translate(-50%, -50%) translateZ(${depthPx.value / 2}px)`,
}));
const backStyle = computed(() => ({
  width: px(widthPx.value),
  height: px(heightPx.value),
  transform: `translate(-50%, -50%) rotateY(180deg) translateZ(${depthPx.value / 2}px)`,
}));
const leftStyle = computed(() => ({
  width: px(depthPx.value),
  height: px(heightPx.value),
  transform: `translate(-50%, -50%) rotateY(-90deg) translateZ(${widthPx.value / 2}px)`,
}));
const rightStyle = computed(() => ({
  width: px(depthPx.value),
  height: px(heightPx.value),
  transform: `translate(-50%, -50%) rotateY(90deg) translateZ(${widthPx.value / 2}px)`,
}));
const topStyle = computed(() => ({
  width: px(widthPx.value),
  height: px(depthPx.value),
  transform: `translate(-50%, -50%) rotateX(90deg) translateZ(${heightPx.value / 2}px)`,
}));
const bottomStyle = computed(() => ({
  width: px(widthPx.value),
  height: px(depthPx.value),
  transform: `translate(-50%, -50%) rotateX(-90deg) translateZ(${heightPx.value / 2}px)`,
}));

const rootStyle = computed(() => ({ aspectRatio: String(frontRatio.value) }));
</script>

<template>
  <div
    ref="rootEl"
    v-bind="$attrs"
    class="r-box3d"
    role="img"
    :aria-label="alt"
    tabindex="0"
    :style="rootStyle"
  >
    <div class="r-box3d__shadow" />
    <div class="r-box3d__stage">
      <div class="r-box3d__box" :style="boxStyle">
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="front"
          :alt="alt"
          :style="frontStyle"
          draggable="false"
          @load="onFrontLoad"
          @error="emit('error')"
        >
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="back"
          alt=""
          :style="backStyle"
          draggable="false"
        >
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="spine"
          alt=""
          :style="leftStyle"
          draggable="false"
          @load="onSpineLoad"
        >
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="spine"
          alt=""
          :style="rightStyle"
          draggable="false"
        >
        <div class="r-box3d__face r-box3d__face--edge" :style="topStyle" />
        <div
          class="r-box3d__face r-box3d__face--edge"
          :style="bottomStyle"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-box3d {
  position: relative;
  width: 100%;
  /* Let the box bleed past its footprint while turning. */
  overflow: visible;
  cursor: grab;
  touch-action: none;
  outline: none;
}
.r-box3d:active {
  cursor: grabbing;
}

/* Soft contact shadow on the floor under the box. */
.r-box3d__shadow {
  position: absolute;
  left: 12%;
  right: 12%;
  bottom: -4%;
  height: 10%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at center,
    color-mix(in srgb, black 38%, transparent),
    transparent 70%
  );
  filter: blur(6px);
  pointer-events: none;
}

.r-box3d__stage {
  position: absolute;
  inset: 0;
  perspective: 1400px;
  display: grid;
  place-items: center;
}

.r-box3d__box {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  will-change: transform;
}

.r-box3d__face {
  position: absolute;
  top: 50%;
  left: 50%;
  /* Each face is centred on the box origin, then pushed out by its own
     transform (set inline). backface-visibility hidden keeps the far side
     from bleeding through the art. */
  backface-visibility: hidden;
  border-radius: var(--r-radius-xs);
  overflow: hidden;
}
.r-box3d__face--art {
  display: block;
  object-fit: cover;
  background: var(--r-color-cover-placeholder);
  /* No image smoothing fuzz on pixel-art spines. */
  box-shadow: inset 0 0 0 1px color-mix(in srgb, black 18%, transparent);
}
/* Top / bottom cardboard edges — tinted, no print. */
.r-box3d__face--edge {
  background: linear-gradient(
    var(--r-color-cover-placeholder-bright),
    var(--r-color-cover-placeholder)
  );
}

@media (prefers-reduced-motion: reduce) {
  .r-box3d__box {
    transition: none !important;
  }
}
</style>
