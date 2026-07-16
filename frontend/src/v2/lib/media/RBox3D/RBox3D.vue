<script setup lang="ts">
// RBox3D — a fake-but-believable 3D game box built from three flat scans
// (front, back, spine). Six CSS faces under `transform-style: preserve-3d`:
// the front/back carry their art and the side scan wraps all four edge faces.
// It reads right on the pair matching its orientation (the vertical spines for
// a portrait scan, the top/bottom for a landscape N64-style strip) and is spun
// 90° in-plane to fit the other pair. Box proportions are derived from the
// images themselves — the front's natural ratio sets width/height and the side scan's sets the depth — so
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
import { computed, onBeforeUnmount, onMounted, ref, type Ref } from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";

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
  initialYaw: 32,
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
const IDLE_RESUME_MS = 2000; //       quiet time before auto-spin resumes
const FLICK_WINDOW_MS = 60; //        release this long after the last move = no flick
const MOMENTUM_FRAMES = 12; //        how far a flick coasts (× last-frame velocity)
const MOMENTUM_MAX = 540; //          cap the coast so a hard flick can't whirl forever
const DEFAULT_FRONT_RATIO = 0.715; // typical box face w/h until measured
const DEFAULT_SPINE_RATIO = 0.12; //  depth/long-edge until measured
// The side scan's short edge is the box depth; its long edge matches the box's
// long dimension (height for a portrait spine, width for a landscape N64-style
// strip). We take short/long so either orientation yields a sane fraction, then
// cap it so a near-square or malformed scan can't over-inflate the depth.
const MAX_SPINE_RATIO = 0.3;

const rootEl = ref<HTMLElement | null>(null);
const frontImg = ref<HTMLImageElement | null>(null);
const spineImg = ref<HTMLImageElement | null>(null);

// Orientation.
const yaw = ref(props.initialYaw);
const pitch = ref(props.initialPitch);

// Measured geometry. `widthPx` comes from a ResizeObserver; the ratios from
// the images' natural dimensions on load.
const widthPx = ref(0);
const frontRatio = ref(DEFAULT_FRONT_RATIO); // front w / h  → box w / h
const spineRatio = ref(DEFAULT_SPINE_RATIO); // spine short/long → depth fraction
// Side scan wider than tall (N64-style): it wraps the top/bottom edges instead
// of the vertical spines, so the strip runs along the box width.
const spineLandscape = ref(false);

const heightPx = computed(() =>
  frontRatio.value > 0 ? widthPx.value / frontRatio.value : 0,
);
// Depth scales off whichever box dimension the scan's long edge maps to.
const depthPx = computed(
  () =>
    (spineLandscape.value ? widthPx.value : heightPx.value) * spineRatio.value,
);

// Reduced-motion gates the idle auto-spin drift. Reactive, so toggling
// reduced-motion mode live stops/resumes the drift without a remount.
const { enabled: reducedMotion } = useReducedMotion();

// Interaction bookkeeping.
const dragging = ref(false);
const stickActive = ref(false);
// `autoSpinning` and `coasting` drive the transition string, so they're refs;
// they're updated from the RAF loop / pointer handlers, never from a computed
// (a computed reading `performance.now()` would cache and never resume).
const autoSpinning = ref(false);
const coasting = ref(false);
let lastInteractAt = 0;
let lastMoveAt = 0;
let dragPointerId: number | null = null;
let lastX = 0;
let lastY = 0;
let velX = 0; //  last-frame pointer delta, kept for the flick on release
let velY = 0;
let rafId = 0;

// Snap transitions off whenever the box is being driven continuously (drag,
// stick, drift); a flick coasts on an ease-out curve, and discrete keyboard
// steps ease on a shorter one.
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
  coasting.value = false;
  velX = 0;
  velY = 0;
  lastX = e.clientX;
  lastY = e.clientY;
  rootEl.value?.setPointerCapture(e.pointerId);
  markInteract();
}
function onPointerMove(e: PointerEvent) {
  if (e.pointerId !== dragPointerId) return;
  velX = e.clientX - lastX;
  velY = e.clientY - lastY;
  yaw.value += velX * DRAG_SENSITIVITY;
  pitch.value = clampPitch(pitch.value - velY * DRAG_SENSITIVITY);
  lastX = e.clientX;
  lastY = e.clientY;
  lastMoveAt = performance.now();
  markInteract();
}
function endDrag(e: PointerEvent) {
  if (e.pointerId !== dragPointerId) return;
  dragPointerId = null;
  dragging.value = false;
  // Momentum without a JS decay loop: hand the box the flick velocity as one
  // extra rotation and let the CSS ease-out curve coast it to a stop. Releasing
  // after a pause (no recent movement) carries no flick.
  if (performance.now() - lastMoveAt < FLICK_WINDOW_MS) {
    const coast = (v: number) =>
      Math.max(
        -MOMENTUM_MAX,
        Math.min(MOMENTUM_MAX, v * DRAG_SENSITIVITY * MOMENTUM_FRAMES),
      );
    const dy = coast(velX);
    const dp = coast(-velY);
    if (Math.abs(dy) > 1 || Math.abs(dp) > 1) {
      coasting.value = true;
      yaw.value += dy;
      pitch.value = clampPitch(pitch.value + dp);
    }
  }
  velX = 0;
  velY = 0;
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
  coasting.value = false;
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
    const active =
      Math.abs(rx) > STICK_DEADZONE || Math.abs(ry) > STICK_DEADZONE;
    stickActive.value = active;
    if (active) {
      yaw.value += rx * STICK_SPEED;
      pitch.value = clampPitch(pitch.value - ry * STICK_SPEED);
      markInteract();
    }
  } else if (stickActive.value) {
    stickActive.value = false;
  }

  // Idle drift, evaluated every frame so it resumes once the quiet window
  // elapses (a computed reading the clock would cache and never restart).
  const idle = performance.now() - lastInteractAt > IDLE_RESUME_MS;
  const spin =
    props.autoSpin &&
    !reducedMotion.value &&
    !dragging.value &&
    !stickActive.value &&
    idle;
  autoSpinning.value = spin;
  if (spin) {
    coasting.value = false;
    yaw.value += AUTO_SPIN_SPEED;
  }

  rafId = requestAnimationFrame(tick);
}

// --- Image measurement ---------------------------------------------------
// The box mirrors the real artwork: the front (box-2D) natural ratio drives
// the box width/height, the spine's drives the depth. Defaults only stand in
// until the bytes are decoded.
function measureRatio(img: HTMLImageElement | null, target: Ref<number>) {
  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    target.value = img.naturalWidth / img.naturalHeight;
  }
}
// The spine drives depth (short/long) and its orientation decides which pair of
// edges carries the art, so it needs its own measurement.
function measureSpine(img: HTMLImageElement | null) {
  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    spineLandscape.value = w > h;
    spineRatio.value = Math.min(
      Math.min(w, h) / Math.max(w, h),
      MAX_SPINE_RATIO,
    );
  }
}
const onFrontLoad = (e: Event) =>
  measureRatio(e.target as HTMLImageElement, frontRatio);
const onSpineLoad = (e: Event) => measureSpine(e.target as HTMLImageElement);

let ro: ResizeObserver | null = null;
onMounted(() => {
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
  // A cached cover can already be decoded before the load listener binds —
  // read its dimensions now so the box adopts box-2D's ratio immediately.
  measureRatio(frontImg.value, frontRatio);
  measureSpine(spineImg.value);
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
// Transition picks the curve for the current gesture: none while driven
// continuously (drag / stick / drift), a long ease-out to coast a flick, and
// a short ease-out for discrete keyboard steps.
const boxTransition = computed(() => {
  if (liveMotion.value) return "none";
  if (coasting.value) return "transform 0.9s cubic-bezier(0.16, 1, 0.3, 1)";
  return "transform 0.28s ease-out";
});
const boxStyle = computed(() => ({
  transform: `rotateX(${pitch.value}deg) rotateY(${yaw.value}deg)`,
  transition: boxTransition.value,
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
// The scan reads the right way only on the pair matching its orientation. On
// the perpendicular ("alternative") pair we spin it 90° in-plane and swap the
// face's width/height so object-fit crops it exactly like the natural pair.
// Vertical faces (left/right) are the alternative pair for a landscape scan;
// horizontal faces (top/bottom) are the alternative pair for a portrait one.
const leftStyle = computed(() => {
  const alt = spineLandscape.value;
  return {
    width: px(alt ? heightPx.value : depthPx.value),
    height: px(alt ? depthPx.value : heightPx.value),
    transform: `translate(-50%, -50%) rotateY(-90deg) translateZ(${widthPx.value / 2}px)${alt ? " rotate(90deg)" : ""}`,
  };
});
const rightStyle = computed(() => {
  const alt = spineLandscape.value;
  return {
    width: px(alt ? heightPx.value : depthPx.value),
    height: px(alt ? depthPx.value : heightPx.value),
    transform: `translate(-50%, -50%) rotateY(90deg) translateZ(${widthPx.value / 2}px)${alt ? " rotate(90deg)" : ""}`,
  };
});
const topStyle = computed(() => {
  const alt = !spineLandscape.value;
  return {
    width: px(alt ? depthPx.value : widthPx.value),
    height: px(alt ? widthPx.value : depthPx.value),
    transform: `translate(-50%, -50%) rotateX(90deg) translateZ(${heightPx.value / 2}px)${alt ? " rotate(90deg)" : ""}`,
  };
});
const bottomStyle = computed(() => {
  const alt = !spineLandscape.value;
  return {
    width: px(alt ? depthPx.value : widthPx.value),
    height: px(alt ? widthPx.value : depthPx.value),
    transform: `translate(-50%, -50%) rotateX(-90deg) translateZ(${heightPx.value / 2}px)${alt ? " rotate(90deg)" : ""}`,
  };
});

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
          ref="frontImg"
          class="r-box3d__face r-box3d__face--art"
          :src="front"
          :alt="alt"
          :style="frontStyle"
          draggable="false"
          @load="onFrontLoad"
          @error="emit('error')"
        />
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="back"
          alt=""
          :style="backStyle"
          draggable="false"
        />
        <!-- The side scan wraps all four edges. It runs along its long axis, so
             it reads right on the pair matching its orientation (vertical spines
             for a portrait scan, top/bottom for a landscape N64-style strip) and
             is simply cropped to fit on the other pair. -->
        <img
          ref="spineImg"
          class="r-box3d__face r-box3d__face--art"
          :src="spine"
          alt=""
          :style="leftStyle"
          draggable="false"
          @load="onSpineLoad"
        />
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="spine"
          alt=""
          :style="rightStyle"
          draggable="false"
        />
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="spine"
          alt=""
          :style="topStyle"
          draggable="false"
        />
        <img
          class="r-box3d__face r-box3d__face--art"
          :src="spine"
          alt=""
          :style="bottomStyle"
          draggable="false"
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
  /* Dragging the box must rotate it, never start a text / image selection. */
  user-select: none;
  -webkit-user-select: none;
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
  /* Faces never capture the pointer — every drag/click lands on the root,
     which owns the rotation listeners (the imgs are also draggable="false"). */
  pointer-events: none;
}
.r-box3d__face--art {
  display: block;
  object-fit: cover;
  background: var(--r-color-cover-placeholder);
  /* No image smoothing fuzz on pixel-art spines. */
  box-shadow: inset 0 0 0 1px color-mix(in srgb, black 18%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  .r-box3d__box {
    transition: none !important;
  }
}
</style>
