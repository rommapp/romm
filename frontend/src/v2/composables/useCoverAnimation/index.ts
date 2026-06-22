// useCoverAnimation — the "juicy" motion layer for alt-art game covers.
//
// v2 port of v1's `useGameAnimation` (which drove a Vuetify VImg; v2 drives a
// raw <img>). Three behaviours, all gated by the card's hover/focus `active`
// signal and the flags `useCoverArt` resolves:
//   * CD spin     — physical art on a CD platform spins up on hover
//                   (accelerate) and coasts down on leave. The launch
//                   flourish spins it at max while it slides down into the
//                   drive and vanishes.
//   * Cartridge   — physical art on a cartridge platform seats fully into
//                   its bay on launch (no hover animation, matching v1).
//   * Hover video — miximage art crossfades to its `path_video` clip a beat
//                   after hover, and resets on leave.
//
// The v1 trick (kept here because it's the part that makes it feel right):
// the slide is `margin-top` with an overshoot transition, while the spin is
// `transform: rotate` — two *different* properties, so they compose. A single
// `transform` for both can't be eased independently (the per-frame spin would
// fight the eased slide).
//
// All motion is gated by the user's `disableAnimations` setting (via
// `motionEnabled`) AND the OS `prefers-reduced-motion`.
import {
  computed,
  onBeforeUnmount,
  ref,
  watch,
  type ComputedRef,
  type Ref,
} from "vue";

export interface SpinConfig {
  /** Top rotational speed, deg/sec. */
  maxSpeed: number;
  /** Acceleration while hovered, deg/sec². */
  accel: number;
  /** Deceleration while not hovered, deg/sec². */
  decel: number;
}

// Mirrors v1's ANIMATION_CONFIG, kept as deg/sec(²) for the frame-rate-
// independent step.
export const SPIN_CONFIG: SpinConfig = {
  maxSpeed: 5000,
  accel: 2500,
  decel: 1500,
};

// Cartridge slot-in depth on launch, as a fraction of the cover height
// (v1 seated at 1/3 on play). There is no cartridge hover animation.
const CART_SEAT_FRACTION = 1 / 3;

// How long the player waits (ms) for the launch flourish before booting —
// the margin transition is 500ms; a little extra lets the motion read.
const CD_LOAD_MS = 700;
const CART_LOAD_MS = 600;

// Delay before the hover video kicks in, so fast scans across the gallery
// don't fire a burst of <video> loads.
const VIDEO_HOVER_DELAY_MS = 1000;

/** Pure one-frame integration of the spin physics — exported for tests.
 *  `accelerating` is true while the cover is hovered/focused; otherwise the
 *  disc coasts to a stop. Velocity is clamped to `[0, maxSpeed]` and the
 *  angle wraps at 360°. */
export function stepSpin(
  state: { angle: number; velocity: number },
  dtSeconds: number,
  accelerating: boolean,
  cfg: SpinConfig = SPIN_CONFIG,
): { angle: number; velocity: number } {
  const rate = accelerating ? cfg.accel : -cfg.decel;
  const velocity = Math.min(
    cfg.maxSpeed,
    Math.max(0, state.velocity + rate * dtSeconds),
  );
  const angle = (state.angle + velocity * dtSeconds) % 360;
  return { angle, velocity };
}

/** True when the OS asks for reduced motion. */
function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export interface UseCoverAnimationOptions {
  /** The cover <img> element (the thing that spins / slides). */
  el: Ref<HTMLElement | null>;
  /** The cover box that clips the slide — used for its `offsetHeight`. */
  containerEl: Ref<HTMLElement | null>;
  /** The hover-video <video> element (miximage style), if rendered. */
  videoEl: Ref<HTMLVideoElement | null>;
  /** Disc-spin applies (physical art, CD-based platform). */
  animateCD: ComputedRef<boolean>;
  /** Cartridge slot-in applies (physical art, non-CD platform). */
  animateCartridge: ComputedRef<boolean>;
  /** Hover-video src (miximage style), or null. */
  videoUrl: ComputedRef<string | null>;
  /** User's animation preference (`!disableAnimations`). */
  motionEnabled: ComputedRef<boolean>;
  /** Hover / focus state of the card — drives the spin / slot-in / video.
   *  The one-shot launch flourish (`playLoad`) is triggered imperatively by
   *  the player view instead. */
  active: Ref<boolean> | ComputedRef<boolean>;
}

export interface UseCoverAnimation {
  /** True while the hover video is actually playing (drives the
   *  image→video crossfade in the card). */
  isVideoPlaying: Ref<boolean>;
  /** Trigger the one-shot launch flourish (disc spin+drop / cartridge
   *  seat). Returns its duration in ms (0 if nothing animates), so the
   *  player view can hold the boot back until the insert plays out. */
  playLoad: () => number;
}

export function useCoverAnimation(
  opts: UseCoverAnimationOptions,
): UseCoverAnimation {
  const motionOk = computed(
    () => opts.motionEnabled.value && !prefersReducedMotion(),
  );

  // The slide (`margin-top`) is eased in CSS (`.game-cover__img`) so it
  // composes with the per-frame `transform: rotate` written below — the spin
  // stays immediate while the slot-in/drop overshoots.

  // ── CD spin (+ launch drop) ───────────────────────────────────────
  let angle = 0;
  let velocity = 0;
  let lastTs: number | null = null;
  let raf: number | null = null;
  // While true the disc holds max speed and slides the full height down
  // into the drive (the launch flourish). Cleared by `stopSpin`.
  let dropping = false;

  function frame(ts: number) {
    const img = opts.el.value;
    if (!img) {
      raf = null;
      return;
    }
    if (lastTs === null) lastTs = ts;
    // Clamp dt so a backgrounded tab doesn't resume with a giant jump.
    const dt = Math.min((ts - lastTs) / 1000, 0.05);
    lastTs = ts;

    const next = stepSpin({ angle, velocity }, dt, opts.active.value);
    angle = next.angle;
    velocity = next.velocity;

    if (dropping) {
      velocity = SPIN_CONFIG.maxSpeed;
      const container = opts.containerEl.value;
      if (container) img.style.marginTop = `${container.offsetHeight}px`;
    }

    img.style.transform = `rotate(${angle.toFixed(2)}deg)`;

    if (velocity > 0 || opts.active.value || dropping) {
      raf = requestAnimationFrame(frame);
    } else {
      stopSpin();
    }
  }

  function kickSpin() {
    if (raf === null) {
      lastTs = null;
      raf = requestAnimationFrame(frame);
    }
  }

  function stopSpin() {
    if (raf !== null) cancelAnimationFrame(raf);
    raf = null;
    lastTs = null;
    angle = 0;
    velocity = 0;
    dropping = false;
    const img = opts.el.value;
    if (img) {
      img.style.transform = "";
      img.style.marginTop = "";
    }
  }

  const wantsSpin = computed(
    () => opts.active.value && opts.animateCD.value && motionOk.value,
  );
  watch(wantsSpin, (on) => {
    if (on) kickSpin();
    // Leaving: the frame loop coasts down on its own (active is false).
  });
  watch(
    () => opts.animateCD.value,
    (cd) => {
      if (!cd) stopSpin();
    },
  );

  // ── Cartridge slot-in ─────────────────────────────────────────────
  // Cartridges only seat on launch (no hover animation — matches v1).
  function cartSlot(depthFraction: number) {
    const img = opts.el.value;
    const container = opts.containerEl.value;
    if (!img || !container) return;
    img.style.transform = "rotate(0deg)";
    img.style.marginTop = depthFraction
      ? `${container.offsetHeight * depthFraction}px`
      : "";
  }

  // ── Launch flourish (player view) ─────────────────────────────────
  function playLoad(): number {
    const img = opts.el.value;
    const container = opts.containerEl.value;
    if (!motionOk.value || !img || !container) return 0;
    if (opts.animateCD.value) {
      // Spin up to max and slide the full height down into the drive.
      dropping = true;
      kickSpin();
      return CD_LOAD_MS;
    }
    if (opts.animateCartridge.value) {
      // Seat the cartridge fully into the bay.
      cartSlot(CART_SEAT_FRACTION);
      return CART_LOAD_MS;
    }
    return 0;
  }

  // ── Hover video ───────────────────────────────────────────────────
  const isVideoPlaying = ref(false);
  let videoTimer: number | null = null;

  const wantsVideo = computed(
    () => opts.active.value && !!opts.videoUrl.value && motionOk.value,
  );

  function scheduleVideo() {
    cancelVideoTimer();
    videoTimer = window.setTimeout(() => {
      const v = opts.videoEl.value;
      if (!v) return;
      v.play()
        .then(() => {
          isVideoPlaying.value = true;
        })
        .catch(() => {
          isVideoPlaying.value = false;
        });
    }, VIDEO_HOVER_DELAY_MS);
  }

  function cancelVideoTimer() {
    if (videoTimer !== null) {
      clearTimeout(videoTimer);
      videoTimer = null;
    }
  }

  function stopVideo() {
    cancelVideoTimer();
    isVideoPlaying.value = false;
    const v = opts.videoEl.value;
    if (v) {
      v.pause();
      v.currentTime = 0;
    }
  }

  watch(wantsVideo, (on) => {
    if (on) scheduleVideo();
    else stopVideo();
  });

  // ── Motion preference flips off mid-flight ────────────────────────
  watch(motionOk, (ok) => {
    if (!ok) {
      stopSpin();
      cartSlot(0);
      stopVideo();
    }
  });

  onBeforeUnmount(() => {
    stopSpin();
    cancelVideoTimer();
    const v = opts.videoEl.value;
    if (v) v.pause();
  });

  return { isVideoPlaying, playLoad };
}
