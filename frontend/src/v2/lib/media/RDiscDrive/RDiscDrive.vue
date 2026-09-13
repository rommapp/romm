<script setup lang="ts">
// RDiscDrive: an interactive optical drive. Pop the tray, put the disc in,
// push the tray shut. A prototype of the launch easter egg that would replace
// the fixed "disc drop" flourish EmulatorJS already awaits before booting.
//
// Fake 3D, no models: the drive is flat rounded rectangles and the disc is a
// circle squashed with `scaleY` to sit in the tray's elliptical well. The spin
// is a `rotate` on an inner element so it composes with that squash instead of
// fighting it (the same two-property trick useCoverAnimation uses).
//
// Universal input (premise 6): pointer drags the disc into the well and the
// tray closed; while focused, the arrow keys nudge the disc and confirm drops
// it in (this is what the gamepad D-pad / left stick and A emit). `skip()` is
// the escape hatch a consumer binds to "just boot it", because a gag that stands
// between someone and their game stops being funny on the second launch.
//
// Primitive boundaries (§II): no stores, no domain knowledge, just a disc
// image and labels. The feature composite decides which rom is on a CD-based
// platform and what happens once the disc is read.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import RBtn from "../../primitives/RBtn/RBtn.vue";

defineOptions({ inheritAttrs: false });

/** closed → open → seated → reading → ready, plus `error` for an empty close. */
export type DriveState =
  "closed" | "open" | "seated" | "reading" | "ready" | "error";

interface Props {
  /** Disc art URL (the rom's physical/disc scan). */
  disc: string;
  /** Accessible label for the disc (the rom title). */
  alt?: string;
  /** Accessible label for the eject button (primitives take text as props). */
  ejectLabel?: string;
  /** Accessible label for the tray itself, which is its own control. */
  trayLabel?: string;
  /** Trim and LED colour. Pass a platform token to theme the drive. */
  accent?: string;
  /** Keep the disc spinning once the drive has read it. */
  autoSpin?: boolean;
  /** Suppress the drive's synthesised servo / clunk / spin-up sounds. */
  muted?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  alt: "",
  ejectLabel: "Eject",
  trayLabel: "Disc tray",
  accent: "var(--r-color-brand-primary)",
  autoSpin: true,
  muted: false,
});

const emit = defineEmits<{
  /** The disc is seated, the tray is shut and the drive has read it. */
  loaded: [];
  /** The tray was pushed shut with nothing in it. */
  rejected: [];
  /** Every state transition, for consumers driving their own chrome. */
  "update:state": [DriveState];
}>();

// Geometry, in percent of the (square) component box, and the single home for
// every measurement the drive is built from. The CSS reads these back as
// custom properties rather than restating them.
const DISC_SIZE = 36;
const TRAY = { left: 7, top: 51, w: 72, h: 30 };
const WELL = { cx: 50, cy: 55, w: 54 }; // in tray coordinates
const SQUASH = 0.42; //                    viewing angle, as a scaleY
const SNAP_RADIUS = 16; //                 how close a dropped disc still seats
const KEY_STEP = 6; //                     percent per arrow press

const WELL_CENTER = {
  x: TRAY.left + (WELL.cx / 100) * TRAY.w,
  y: TRAY.top + (WELL.cy / 100) * TRAY.h,
};
// Where a disc sits once seated, as the top-left of its (square) box.
const SEAT = {
  x: WELL_CENTER.x - DISC_SIZE / 2,
  y: WELL_CENTER.y - DISC_SIZE / 2,
};
// Sharing the seat's x means the disc drops straight down into the well.
const DOCK = { x: SEAT.x, y: 4 };
// The same spot in the tray's own coordinates, for the disc that rides it.
const SEAT_IN_TRAY = {
  x: ((SEAT.x - TRAY.left) / TRAY.w) * 100,
  y: ((SEAT.y - TRAY.top) / TRAY.h) * 100,
};

// Durations (ms). The tray stroke is the slow one; everything else punctuates.
const TRAY_MS = 900;
const INSERT_MS = 420;
const SPINUP_MS = 900;
const ERROR_MS = 900;

const rootEl = ref<HTMLElement | null>(null);
const state = ref<DriveState>("closed");
// Tray extension, 0 (in) to 1 (out). The visual truth: `state` says what the
// drive is doing, this says where the tray actually is, and a drag writes it
// directly so the tray tracks the finger instead of easing toward a target.
const trayOut = ref(0);
const discPos = ref({ ...DOCK });
const discDragging = ref(false);
const trayDragging = ref(false);
const spin = ref(0);

const { enabled: reducedMotion } = useReducedMotion();

// Reduced motion keeps every state transition and outcome, and drops only the
// travel time, so the drive still opens, reads and reports without the motion.
const ms = (full: number) => (reducedMotion.value ? 0 : full);

let timer: ReturnType<typeof setTimeout> | null = null;
let rafId = 0;
let audioCtx: AudioContext | null = null;

function setState(next: DriveState) {
  if (state.value === next) return;
  state.value = next;
  emit("update:state", next);
}

function later(fn: () => void, delay: number) {
  clearPending();
  timer = setTimeout(fn, ms(delay));
}

function clearPending() {
  if (timer) clearTimeout(timer);
  timer = null;
}

// --- Sound ---------------------------------------------------------------
// Synthesised, so the drive carries no audio assets. Every trigger is a user
// gesture, which is what lets the context start under autoplay policy.
function tone(
  type: OscillatorType,
  from: number,
  to: number,
  duration: number,
  gain: number,
) {
  if (props.muted || typeof window === "undefined" || !window.AudioContext) {
    return;
  }
  if (!audioCtx) audioCtx = new window.AudioContext();
  const ctx = audioCtx;
  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const amp = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(from, now);
  osc.frequency.exponentialRampToValueAtTime(Math.max(to, 1), now + duration);
  amp.gain.setValueAtTime(0, now);
  amp.gain.linearRampToValueAtTime(gain, now + 0.02);
  amp.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  osc.connect(amp).connect(ctx.destination);
  osc.start(now);
  osc.stop(now + duration + 0.05);
}

const sfx = {
  servo: () => tone("sawtooth", 180, 140, 0.5, 0.02),
  clunk: () => tone("square", 140, 50, 0.09, 0.05),
  seat: () => tone("triangle", 520, 300, 0.12, 0.04),
  spinUp: () => tone("sawtooth", 120, 900, 0.8, 0.025),
  reject: () => tone("square", 300, 120, 0.25, 0.05),
};

// --- Transitions ---------------------------------------------------------
function openTray() {
  if (state.value === "reading") return;
  // Ejecting mid-close abandons that close rather than letting its outcome
  // land on a tray that is now open again.
  clearPending();
  sfx.servo();
  trayOut.value = 1;
  // A disc already in the drive comes back out sitting on the tray.
  const loaded = state.value === "seated" || state.value === "ready";
  if (loaded) discPos.value = { ...SEAT };
  setState(loaded ? "seated" : "open");
}

function closeTray() {
  if (trayOut.value === 0) return;
  sfx.servo();
  trayOut.value = 0;
  const hadDisc = state.value === "seated";
  later(() => {
    sfx.clunk();
    if (!hadDisc) {
      setState("error");
      emit("rejected");
      // Spit the tray back out so the mistake is recoverable without hunting
      // for the eject button again.
      later(openTray, ERROR_MS);
      sfx.reject();
      return;
    }
    setState("reading");
    sfx.spinUp();
    later(() => {
      setState("ready");
      emit("loaded");
    }, SPINUP_MS);
  }, TRAY_MS);
}

function toggleTray() {
  if (trayOut.value > 0.5) closeTray();
  else openTray();
}

/** Seat the disc in the well (from a drop, or confirm on the disc). */
function insert() {
  if (state.value !== "open") return;
  discPos.value = { ...SEAT };
  sfx.seat();
  later(() => setState("seated"), INSERT_MS);
}

/** Skip the whole performance and report the disc as read. */
function skip() {
  clearPending();
  trayOut.value = 0;
  discPos.value = { ...SEAT };
  setState("ready");
  emit("loaded");
}

function reset() {
  clearPending();
  trayOut.value = 0;
  discPos.value = { ...DOCK };
  spin.value = 0;
  setState("closed");
}

// --- Pointer -------------------------------------------------------------
// Percent-of-box is the component's coordinate system, so every pointer delta
// converts through the root's measured width before it moves anything.
function pctPerPx() {
  const w = rootEl.value?.clientWidth ?? 0;
  return w > 0 ? 100 / w : 0;
}

let discPointerId: number | null = null;
let trayPointerId: number | null = null;
let lastX = 0;
let lastY = 0;

function onDiscDown(e: PointerEvent) {
  if (state.value !== "open" || discPointerId !== null) return;
  discPointerId = e.pointerId;
  discDragging.value = true;
  lastX = e.clientX;
  lastY = e.clientY;
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
}

function onDiscMove(e: PointerEvent) {
  if (e.pointerId !== discPointerId) return;
  const k = pctPerPx();
  discPos.value = {
    x: discPos.value.x + (e.clientX - lastX) * k,
    y: discPos.value.y + (e.clientY - lastY) * k,
  };
  lastX = e.clientX;
  lastY = e.clientY;
}

function onDiscUp(e: PointerEvent) {
  if (e.pointerId !== discPointerId) return;
  discPointerId = null;
  discDragging.value = false;
  dropDisc();
}

/** Seat the disc if it landed near the well, otherwise send it back. */
function dropDisc() {
  const dx = discPos.value.x - SEAT.x;
  const dy = discPos.value.y - SEAT.y;
  if (Math.hypot(dx, dy) <= SNAP_RADIUS) insert();
  else discPos.value = { ...DOCK };
}

function onTrayDown(e: PointerEvent) {
  if (trayPointerId !== null || state.value === "reading") return;
  trayPointerId = e.pointerId;
  trayDragging.value = true;
  lastY = e.clientY;
  (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
}

function onTrayMove(e: PointerEvent) {
  if (e.pointerId !== trayPointerId) return;
  const stroke = TRAY.h / pctPerPx(); // tray stroke in px
  if (stroke > 0) {
    const next = trayOut.value + (e.clientY - lastY) / stroke;
    trayOut.value = Math.max(0, Math.min(1, next));
  }
  lastY = e.clientY;
}

function onTrayUp(e: PointerEvent) {
  if (e.pointerId !== trayPointerId) return;
  trayPointerId = null;
  trayDragging.value = false;
  // Past halfway the tray commits in the direction it was pushed, so a short
  // shove finishes the stroke rather than leaving the tray hanging.
  if (trayOut.value < 0.5) closeTray();
  else openTray();
}

// --- Keyboard (and so the gamepad D-pad / left stick / A) ----------------
function onDiscKeydown(e: KeyboardEvent) {
  if (state.value !== "open") return;
  const move = (dx: number, dy: number) => {
    discPos.value = { x: discPos.value.x + dx, y: discPos.value.y + dy };
  };
  switch (e.key) {
    case "ArrowLeft":
      move(-KEY_STEP, 0);
      break;
    case "ArrowRight":
      move(KEY_STEP, 0);
      break;
    case "ArrowUp":
      move(0, -KEY_STEP);
      break;
    case "ArrowDown":
      move(0, KEY_STEP);
      break;
    case "Enter":
    case " ":
      insert();
      break;
    default:
      return;
  }
  // Consume so the arrow doesn't also navigate away from a disc mid-insert.
  e.preventDefault();
  e.stopPropagation();
}

function onTrayKeydown(e: KeyboardEvent) {
  switch (e.key) {
    case "ArrowUp":
    case "Enter":
    case " ":
      closeTray();
      break;
    case "ArrowDown":
      openTray();
      break;
    default:
      return;
  }
  e.preventDefault();
  e.stopPropagation();
}

// --- Spin ----------------------------------------------------------------
// Reading spins fast, ready coasts. Driven per frame rather than by a CSS
// animation so the two speeds hand over without a restart jump.
function tick() {
  const speed =
    state.value === "reading"
      ? 9
      : state.value === "ready" && props.autoSpin
        ? 3
        : 0;
  if (speed > 0 && !reducedMotion.value)
    spin.value = (spin.value + speed) % 360;
  rafId = requestAnimationFrame(tick);
}

onMounted(() => {
  rafId = requestAnimationFrame(tick);
});
onBeforeUnmount(() => {
  cancelAnimationFrame(rafId);
  clearPending();
  void audioCtx?.close();
});

// The disc rides the tray once seated, so its resting spot shifts with the
// tray's own stroke while the drive is closing.
watch(trayOut, (v) => {
  if (state.value === "seated" || state.value === "reading") {
    discPos.value = { x: SEAT.x, y: SEAT.y - (1 - v) * TRAY.h };
  }
});

// Clipped away when retracted, so it leaves the focus order with it.
const trayReachable = computed(() => trayOut.value > 0);

const hasDisc = computed(
  () =>
    state.value === "seated" ||
    state.value === "reading" ||
    state.value === "ready",
);
const discFree = computed(
  () => state.value === "open" || state.value === "closed",
);
const ledTone = computed(() => {
  if (state.value === "error") return "var(--r-color-danger)";
  if (state.value === "ready") return "var(--r-color-success)";
  if (state.value === "reading") return props.accent;
  return "var(--r-color-border-strong)";
});

const rootStyle = computed<Record<string, string>>(() => ({
  "--r-dd-accent": props.accent,
  "--r-dd-tray": String(trayOut.value),
  "--r-dd-spin": `${spin.value}deg`,
  "--r-dd-led": ledTone.value,
  "--r-dd-tray-ms": `${ms(TRAY_MS)}ms`,
  "--r-dd-insert-ms": `${ms(INSERT_MS)}ms`,
  "--r-dd-disc": `${DISC_SIZE}%`,
  // Seated, the disc is a child of the tray, so its size restates itself in
  // the tray's narrower coordinates to keep the same absolute diameter.
  "--r-dd-disc-seated": `${(DISC_SIZE / TRAY.w) * 100}%`,
  "--r-dd-bay-x": `${TRAY.left}%`,
  "--r-dd-bay-y": `${TRAY.top}%`,
  "--r-dd-bay-w": `${TRAY.w}%`,
  "--r-dd-bay-h": `${100 - TRAY.top}%`,
  // The tray's height as a share of the bay it is clipped by.
  "--r-dd-tray-h": `${(TRAY.h / (100 - TRAY.top)) * 100}%`,
  "--r-dd-well-x": `${WELL.cx}%`,
  "--r-dd-well-y": `${WELL.cy}%`,
  "--r-dd-well-w": `${WELL.w}%`,
  "--r-dd-flat": String(SQUASH),
  "--r-dd-seat-x": `${SEAT_IN_TRAY.x}%`,
  "--r-dd-seat-y": `${SEAT_IN_TRAY.y}%`,
}));

// Squashed into the tray's plane once it is being laid down; upright in hand.
const discStyle = computed<Record<string, string>>(() => ({
  left: `${discPos.value.x}%`,
  top: `${discPos.value.y}%`,
  "--r-dd-squash": String(discFree.value && !hasDisc.value ? 1 : SQUASH),
  transition: discDragging.value
    ? "none"
    : `left var(--r-dd-insert-ms) var(--r-motion-ease-out), top var(--r-dd-insert-ms) var(--r-motion-ease-out)`,
}));

const trayStyle = computed<Record<string, string>>(() => ({
  transition: trayDragging.value
    ? "none"
    : `transform var(--r-dd-tray-ms) var(--r-motion-ease-in-out)`,
}));

defineExpose({
  /** Current drive state, for consumers that poll rather than listen. */
  state,
  open: openTray,
  close: closeTray,
  insert,
  /** Escape hatch: report the disc read immediately, no performance. */
  skip,
  reset,
});
</script>

<template>
  <div
    ref="rootEl"
    v-bind="$attrs"
    class="r-disc-drive"
    :class="`r-disc-drive--${state}`"
    :style="rootStyle"
  >
    <!-- Chassis -->
    <div class="r-disc-drive__body">
      <div class="r-disc-drive__slot"></div>
      <div class="r-disc-drive__led"></div>
      <RBtn
        class="r-disc-drive__eject"
        icon="mdi-eject"
        size="small"
        variant="translucent"
        :aria-label="ejectLabel"
        @click="toggleTray"
      />
    </div>

    <!-- Bay: clips the tray to the drive's mouth. Transparent to the pointer
         so the eject button beside it stays clickable. -->
    <div class="r-disc-drive__bay">
      <div
        class="r-disc-drive__tray"
        :style="trayStyle"
        role="button"
        :tabindex="trayReachable ? 0 : -1"
        :aria-hidden="!trayReachable"
        :aria-label="trayLabel"
        @pointerdown="onTrayDown"
        @pointermove="onTrayMove"
        @pointerup="onTrayUp"
        @pointercancel="onTrayUp"
        @keydown="onTrayKeydown"
      >
        <div class="r-disc-drive__well"></div>
        <div class="r-disc-drive__spindle"></div>
        <!-- Seated: the disc rides the tray, and the bay swallows it on close. -->
        <div
          v-if="hasDisc"
          class="r-disc-drive__disc r-disc-drive__disc--seated"
        >
          <div class="r-disc-drive__disc-body">
            <img
              class="r-disc-drive__art"
              :src="disc"
              :alt="alt"
              draggable="false"
            />
            <div class="r-disc-drive__sheen"></div>
            <div class="r-disc-drive__hub"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Loose: the disc in hand, draggable into the well. -->
    <div
      v-if="!hasDisc"
      class="r-disc-drive__disc r-disc-drive__disc--free"
      :class="{ 'r-disc-drive__disc--held': discDragging }"
      :style="discStyle"
      role="button"
      tabindex="0"
      :aria-label="alt"
      @pointerdown="onDiscDown"
      @pointermove="onDiscMove"
      @pointerup="onDiscUp"
      @pointercancel="onDiscUp"
      @keydown="onDiscKeydown"
    >
      <div class="r-disc-drive__disc-body">
        <img
          class="r-disc-drive__art"
          :src="disc"
          :alt="alt"
          draggable="false"
        />
        <div class="r-disc-drive__sheen"></div>
        <div class="r-disc-drive__hub"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-disc-drive {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  user-select: none;
  touch-action: none;
}

/* Chassis ---------------------------------------------------------------- */
.r-disc-drive__body {
  position: absolute;
  inset: 46% 0 0 0;
  border-radius: var(--r-radius-card);
  border: 1px solid var(--r-color-panel-border);
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, white 6%, var(--r-color-panel)),
    var(--r-color-panel)
  );
  box-shadow: var(--r-elev-3);
}

.r-disc-drive__slot {
  position: absolute;
  left: 5%;
  top: 8%;
  width: 76%;
  height: 9%;
  border-radius: var(--r-radius-pill);
  background: color-mix(in srgb, black 55%, transparent);
  box-shadow: inset 0 2px 4px color-mix(in srgb, black 60%, transparent);
}

.r-disc-drive__led {
  position: absolute;
  right: 8%;
  top: 12%;
  width: 5%;
  aspect-ratio: 1;
  border-radius: var(--r-radius-full);
  background: var(--r-dd-led);
  box-shadow: 0 0 8px var(--r-dd-led);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-disc-drive--reading .r-disc-drive__led {
  animation: r-dd-blink 0.35s steps(1) infinite;
}

@keyframes r-dd-blink {
  50% {
    opacity: 0.25;
  }
}

.r-disc-drive__eject {
  position: absolute;
  right: 4%;
  bottom: 10%;
}

/* Tray ------------------------------------------------------------------- */
.r-disc-drive__bay {
  position: absolute;
  left: var(--r-dd-bay-x);
  top: var(--r-dd-bay-y);
  width: var(--r-dd-bay-w);
  height: var(--r-dd-bay-h);
  overflow: hidden;
  pointer-events: none;
  z-index: 1;
}

.r-disc-drive__tray {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: var(--r-dd-tray-h);
  pointer-events: auto;
  cursor: grab;
  border-radius: 0 0 var(--r-radius-md) var(--r-radius-md);
  border: 1px solid var(--r-color-border-strong);
  border-top: none;
  background: var(--r-color-bg-elevated);
  box-shadow:
    0 14px 22px color-mix(in srgb, black 45%, transparent),
    inset 0 -6px 10px -6px color-mix(in srgb, black 40%, transparent);
  /* Fully retracted the tray sits above the bay, so the bay clips it away. */
  transform: translateY(calc((var(--r-dd-tray) - 1) * 100%));
}

.r-disc-drive__tray:active {
  cursor: grabbing;
}

.r-disc-drive__well {
  position: absolute;
  left: var(--r-dd-well-x);
  top: var(--r-dd-well-y);
  width: var(--r-dd-well-w);
  aspect-ratio: 1 / 0.42;
  transform: translate(-50%, -50%);
  border-radius: var(--r-radius-full);
  background: color-mix(in srgb, black 45%, transparent);
  box-shadow:
    inset 0 2px 6px color-mix(in srgb, black 60%, transparent),
    0 0 0 1px color-mix(in srgb, white 12%, transparent);
}

.r-disc-drive__spindle {
  position: absolute;
  left: var(--r-dd-well-x);
  top: var(--r-dd-well-y);
  width: 6%;
  aspect-ratio: 1 / 0.42;
  transform: translate(-50%, -50%);
  border-radius: var(--r-radius-full);
  background: var(--r-color-border-strong);
}

/* Disc ------------------------------------------------------------------- */
.r-disc-drive__disc {
  position: absolute;
  width: var(--r-dd-disc);
  aspect-ratio: 1;
  z-index: 2;
}

.r-disc-drive__disc--free {
  cursor: grab;
}

.r-disc-drive__disc--held {
  cursor: grabbing;
  filter: drop-shadow(0 12px 16px color-mix(in srgb, black 50%, transparent));
}

/* Seated, the disc is positioned in the tray's own coordinates so it rides
   the stroke; loose, the drag writes left/top directly. */
.r-disc-drive__disc--seated {
  width: var(--r-dd-disc-seated);
  left: var(--r-dd-seat-x);
  top: var(--r-dd-seat-y);
  --r-dd-squash: var(--r-dd-flat);
}

/* Squash is the viewing angle, rotate is the spin: separate properties so
   neither has to be folded into the other's easing. */
.r-disc-drive__disc-body {
  position: absolute;
  inset: 0;
  border-radius: var(--r-radius-full);
  overflow: hidden;
  transform: scaleY(var(--r-dd-squash, 1)) rotate(var(--r-dd-spin));
  transition: transform var(--r-dd-insert-ms) var(--r-motion-ease-out);
  box-shadow: 0 0 0 1px color-mix(in srgb, white 18%, transparent);
}

.r-disc-drive--reading .r-disc-drive__disc-body,
.r-disc-drive--ready .r-disc-drive__disc-body {
  transition: none;
}

.r-disc-drive__art {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: var(--r-radius-full);
}

.r-disc-drive__sheen {
  position: absolute;
  inset: 0;
  border-radius: var(--r-radius-full);
  background: conic-gradient(
    from 0deg,
    transparent 0deg,
    color-mix(in srgb, white 35%, transparent) 25deg,
    transparent 60deg,
    transparent 180deg,
    color-mix(in srgb, white 22%, transparent) 205deg,
    transparent 240deg
  );
  mix-blend-mode: screen;
  pointer-events: none;
}

.r-disc-drive__hub {
  position: absolute;
  left: 38%;
  top: 38%;
  width: 24%;
  aspect-ratio: 1;
  border-radius: var(--r-radius-full);
  background: var(--r-color-bg);
  box-shadow: inset 0 0 0 6px color-mix(in srgb, white 12%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  .r-disc-drive__led {
    animation: none;
  }
}
</style>
