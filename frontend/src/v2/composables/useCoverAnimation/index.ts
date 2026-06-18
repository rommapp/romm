// useCoverAnimation — the "juicy" motion layer for alt-art game covers.
//
// v2 rebuild of v1's deprecated `useGameAnimation` against a raw <img>
// (v2 has no Vuetify VImg internals). Three behaviours, all driven by the
// card's hover/focus `active` signal and the flags `useCoverArt` resolves:
//   * CD spin      — physical art on a CD-based platform spins up on
//                    hover (accelerate) and coasts down on leave.
//   * Cartridge     — physical art on a cartridge platform does a one-shot
//                    "slot-in" drop when first hovered.
//   * Hover video   — miximage art crossfades to its `path_video` clip a
//                    beat after hover, and resets on leave.
//
// All motion is gated by the user's `disableAnimations` setting (via
// `motionEnabled`) AND the OS `prefers-reduced-motion` — when either says
// no, the cover stays a still image.
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

// Mirrors v1's ANIMATION_CONFIG (maxRotationSpeed / acceleration /
// deceleration), kept as deg/sec(²) for the frame-rate-independent step.
export const SPIN_CONFIG: SpinConfig = {
  maxSpeed: 5000,
  accel: 2500,
  decel: 1500,
};

// Delay before the hover video kicks in, so fast scans across the gallery
// don't fire a burst of <video> loads. A touch snappier than v1's 1500ms.
const VIDEO_HOVER_DELAY_MS = 1000;

/** Pure one-frame integration of the spin physics — exported for tests.
 *  `accelerating` is true while the cover is hovered/focused; otherwise
 *  the disc coasts to a stop. Velocity is clamped to `[0, maxSpeed]` and
 *  the angle wraps at 360°. */
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
  /** The cover <img> element (the thing that spins / slots in). */
  el: Ref<HTMLElement | null>;
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
  /** Hover / focus state of the card — drives the spin / video. The
   *  one-shot launch flourish (`playLoad`) is triggered imperatively by
   *  the player view instead. */
  active: Ref<boolean> | ComputedRef<boolean>;
}

export interface UseCoverAnimation {
  /** True while the hover video is actually playing (drives the
   *  image→video crossfade in the card). */
  isVideoPlaying: Ref<boolean>;
  /** Trigger the one-shot launch flourish (disc drop+spin / cartridge
   *  slot-in). Returns its duration in ms (0 if nothing animates), so the
   *  player view can hold the boot back until the insert plays out. */
  playLoad: () => number;
}

export function useCoverAnimation(
  opts: UseCoverAnimationOptions,
): UseCoverAnimation {
  const motionOk = computed(
    () => opts.motionEnabled.value && !prefersReducedMotion(),
  );

  // ── CD spin ───────────────────────────────────────────────────────
  let angle = 0;
  let velocity = 0;
  let lastTs: number | null = null;
  let raf: number | null = null;

  const wantsSpin = computed(
    () => opts.active.value && opts.animateCD.value && motionOk.value,
  );

  function frame(ts: number) {
    if (lastTs === null) lastTs = ts;
    // Clamp dt so a backgrounded tab doesn't resume with a giant jump.
    const dt = Math.min((ts - lastTs) / 1000, 0.05);
    lastTs = ts;

    const next = stepSpin({ angle, velocity }, dt, wantsSpin.value);
    angle = next.angle;
    velocity = next.velocity;

    // Use the individual `rotate` property (not `transform`) so the
    // drop-in animation can own `transform: translateY` and the two
    // compose instead of clobbering each other.
    if (opts.el.value) {
      opts.el.value.style.rotate = `${angle.toFixed(2)}deg`;
    }

    if (velocity > 0 || wantsSpin.value) {
      raf = requestAnimationFrame(frame);
    } else {
      // Fully stopped — clear so a later style switch doesn't leave a
      // stale rotation on a non-disc image.
      raf = null;
      lastTs = null;
      angle = 0;
      velocity = 0;
      if (opts.el.value) opts.el.value.style.rotate = "";
    }
  }

  function kickSpin() {
    if (raf === null) {
      lastTs = null;
      raf = requestAnimationFrame(frame);
    }
  }

  function hardStopSpin() {
    if (raf !== null) cancelAnimationFrame(raf);
    raf = null;
    lastTs = null;
    angle = 0;
    velocity = 0;
    if (opts.el.value) opts.el.value.style.rotate = "";
  }

  // Start coasting up when wanted; the frame loop coasts down on its own
  // once `wantsSpin` flips false. A style switch away from CD hard-stops
  // so we don't keep spinning a cartridge / box.
  watch(wantsSpin, (on) => {
    if (on) kickSpin();
  });
  watch(
    () => opts.animateCD.value,
    (cd) => {
      if (!cd) hardStopSpin();
    },
  );

  // ── Drop-in (cartridge slot-in / disc drop) ───────────────────────
  // One-shot translateY with an overshoot settle. Uses `transform` so it
  // composes with the spin's `rotate` property. `from` is the start
  // offset as a percentage of the element height.
  function dropIn(from: number, duration: number) {
    const el = opts.el.value;
    if (!el || typeof el.animate !== "function") return;
    el.animate(
      [
        { transform: `translateY(${from}%)`, opacity: 0.85, offset: 0 },
        { transform: "translateY(4%)", offset: 0.72 },
        { transform: "translateY(0)", opacity: 1, offset: 1 },
      ],
      { duration, easing: "cubic-bezier(0.34, 1.56, 0.64, 1)" },
    );
  }

  // Gentle slot-in when a cartridge cover is first hovered.
  function playInsert() {
    dropIn(-16, 440);
  }

  // Launch "load" flourish (player view): from its RESTING position the
  // disc spins up and slides DOWN into the drive, or the cartridge slides
  // down into the slot. One self-contained Web Animations keyframe (not the
  // rAF spin loop). `fill: forwards` keeps it inserted until the hero
  // unmounts for the running game. Returns the duration in ms (0 when no
  // launch animation applies) so the caller can hold the boot back until
  // the insert is seen. Starts at translateY(0) — no upward jump.
  // Disc: spins up and slides ALL the way down into the drive, vanishing.
  const CD_LOAD_MS = 850;
  // Cartridge: slides DOWN to ~halfway (clipped by the slot edge) and
  // HOLDS there ~1s, as if seated/connected — then the game boots.
  const CART_LOAD_MS = 1250;
  function playLoad(): number {
    const el = opts.el.value;
    if (!motionOk.value || !el || typeof el.animate !== "function") return 0;
    hardStopSpin();
    if (opts.animateCD.value) {
      el.animate(
        [
          { transform: "translateY(0) rotate(0deg)", opacity: 1, offset: 0 },
          {
            transform: "translateY(10%) rotate(240deg)",
            opacity: 1,
            offset: 0.28,
          },
          {
            transform: "translateY(130%) rotate(1120deg)",
            opacity: 0,
            offset: 1,
          },
        ],
        {
          duration: CD_LOAD_MS,
          easing: "cubic-bezier(0.5, 0, 0.9, 0.3)",
          fill: "forwards",
        },
      );
      return CD_LOAD_MS;
    }
    if (opts.animateCartridge.value) {
      el.animate(
        [
          {
            transform: "translateY(0)",
            offset: 0,
            easing: "cubic-bezier(0.34, 1.1, 0.5, 1)",
          },
          { transform: "translateY(50%)", offset: 0.28 }, // seated halfway
          { transform: "translateY(50%)", offset: 1 }, // hold ~1s
        ],
        { duration: CART_LOAD_MS, fill: "forwards" },
      );
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

  // ── Active-edge: fire the one-shot cartridge insert ───────────────
  watch(
    () => opts.active.value,
    (now, prev) => {
      if (now && !prev && opts.animateCartridge.value && motionOk.value) {
        playInsert();
      }
    },
  );

  // ── Motion preference flips off mid-flight ────────────────────────
  watch(motionOk, (ok) => {
    if (!ok) {
      hardStopSpin();
      stopVideo();
    }
  });

  onBeforeUnmount(() => {
    hardStopSpin();
    cancelVideoTimer();
    const v = opts.videoEl.value;
    if (v) v.pause();
  });

  return { isVideoPlaying, playLoad };
}
