// useGamepad
//
// Universal gamepad support. Translates D-pad / left-stick presses into
// synthetic KeyboardEvents so the normal DOM focus model and Vue click
// handlers work out of the box on a controller — no bespoke spatial-nav
// engine required. Face buttons run direct actions (click the focused
// element, open a menu, nav sections) because synthetic keyboard events
// have `isTrusted=false` and don't trigger the default activation
// behaviour on <a href> / <button type="submit"> — a direct .click() is
// the only reliable path there.
//
// Mapping (Standard Gamepad):
//   D-pad up / down / left / right → Arrow{Up,Down,Left,Right}
//   Left stick (above threshold)   → Arrow* (with initial delay + repeat)
//   A button (0)                   → activate focused element (click)
//   B button (1)                   → Escape
//   Back / Select (8)              → Escape
//   Start (9)                      → open user menu
//   LB (4) / RB (5)                → AppNav section prev / next (cyclic)
//
// Action buttons (A/B/Back/Start/LB/RB) fire once per press — no repeat —
// so a held face button doesn't shotgun actions. Synthetic-key buttons
// (arrows) use the v1 console input cadence: 350ms initial delay, 120ms
// repeat.
//
// Two contexts suppress this translation:
//   * Game running (storePlaying.playing) — the emulator reads the pad
//     itself, so all translation is off. Otherwise B (shared by Circle /
//     Nintendo-A in the standard mapping) would quit the game.
//   * Controller-test screen (ACTIONS_DISABLED_PATHS) — built-in actions
//     are muted so every button can be pressed and inspected in place.
import { onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import storePlaying from "@/stores/playing";
import { useInputModality } from "@/v2/composables/useInputModality";
import {
  closeTopEscapable,
  hasOpenEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack.js";

// AppNav tab order — must match the `tabs` list in
// `src/v2/components/AppShell/AppNav.vue`. LB/RB cycle through these.
const NAV_SECTIONS = ["/", "/platforms", "/collections", "/search"] as const;

// Routes where useGamepad's built-in actions (back, activate, section
// nav, user menu) must NOT fire, so every button stays inspectable in
// place. The controller-debug "test" screen needs this: otherwise B
// pops history and A clicks before the press can even be seen.
const ACTIONS_DISABLED_PATHS = new Set<string>(["/controller-debug"]);

const INITIAL_DELAY_MS = 350;
const REPEAT_MS = 120;
const AXIS_THRESHOLD = 0.5;

// Standard-mapping button index → short symbolic name. Used as the
// `name` field on the `gamepad:buttondown` custom event so views can
// filter without memorising W3C indices. Kept exhaustive over the
// standard 0..16 range; anything past that ships as `name: undefined`.
const BUTTON_NAMES: Record<number, string> = {
  0: "a",
  1: "b",
  2: "x",
  3: "y",
  4: "lb",
  5: "rb",
  6: "lt",
  7: "rt",
  8: "back",
  9: "start",
  10: "l3",
  11: "r3",
  12: "dpad-up",
  13: "dpad-down",
  14: "dpad-left",
  15: "dpad-right",
  16: "home",
};

export interface GamepadButtonEventDetail {
  /** W3C standard-mapping button index. */
  index: number;
  /** Symbolic name (e.g. "y", "rt", "dpad-up"). Undefined past 16. */
  name?: string;
}

// Augment the global event map so listeners get typed `detail`s
// without per-call-site casts.
declare global {
  interface WindowEventMap {
    "gamepad:buttondown": CustomEvent<GamepadButtonEventDetail>;
  }
}

type Binding = { key: string; code?: string };

// Standard gamepad button index → synthetic keyboard event. Only the
// navigational keys live here (arrows); face buttons and bumpers get
// handled by BUTTON_ACTIONS below where a .click() / router.push() can
// actually do the thing.
const BUTTON_MAP: Record<number, Binding | undefined> = {
  12: { key: "ArrowUp", code: "ArrowUp" },
  13: { key: "ArrowDown", code: "ArrowDown" },
  14: { key: "ArrowLeft", code: "ArrowLeft" },
  15: { key: "ArrowRight", code: "ArrowRight" },
};

// Guards the polling loop against phantom gamepads.
// Firefox keeps disconnected entries in the getGamepads() array,
// and their stale analog values drift across the press threshold,
// firing index-based actions with no user input. #3851.
function isUsablePad(pad: Gamepad | null): pad is Gamepad {
  return pad !== null && pad.connected;
}

function dispatchKey(binding: Binding) {
  const target =
    (document.activeElement as HTMLElement | null) ?? document.body;
  const init: KeyboardEventInit = {
    key: binding.key,
    code: binding.code,
    bubbles: true,
    cancelable: true,
  };
  target.dispatchEvent(new KeyboardEvent("keydown", init));
  target.dispatchEvent(new KeyboardEvent("keyup", init));
}

type ButtonState = { pressed: boolean; nextRepeatAt: number };
type PadState = {
  buttons: Record<number, ButtonState>;
  axisNextAt: { x: number; y: number };
};

let installed = false;

export function useGamepad() {
  // Resolved here (setup context) so install() can reach them from inside
  // the RAF loop without needing the component instance.
  const router = useRouter();
  const route = useRoute();

  const playingStore = storePlaying();

  function cycleSection(step: -1 | 1) {
    const currentPath = route.path;

    // Match current section by path prefix so /platform/:id still registers
    // as "/platforms" when LB/RB is pressed from a gallery sub-route.
    const matchIndex = NAV_SECTIONS.findIndex((section) =>
      section === "/" ? currentPath === "/" : currentPath.startsWith(section),
    );
    // Not on a section at all (e.g. on /rom/:id). Jumping straight to
    // Home is more predictable than silently treating the current page
    // as Home and stepping once — that used to take the user to
    // Platforms when pressing RB from a ROM detail view.
    if (matchIndex < 0) {
      if (currentPath !== "/") router.push("/");
      return;
    }
    const nextIndex =
      (matchIndex + step + NAV_SECTIONS.length) % NAV_SECTIONS.length;
    const target = NAV_SECTIONS[nextIndex];
    if (target !== currentPath) router.push(target);
  }

  // Activates the currently focused element. Router-links, submit
  // buttons, custom [role=button] divs all navigate/trigger via .click()
  // regardless of whether the event was trusted — that's the escape
  // hatch synthetic KeyboardEvents don't give us.
  function activateFocused() {
    const active = document.activeElement as HTMLElement | null;
    if (!active) return;
    // Skip text inputs etc. — pressing A inside a text field shouldn't
    // re-submit the form on every press.
    const tag = active.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    active.click();
  }

  // Opens the app-wide user menu. UserMenu.vue marks its activator with
  // `data-user-menu-trigger` so we can find it regardless of which view
  // is mounted — the nav is always in the DOM.
  function openUserMenu() {
    const trigger = document.querySelector<HTMLElement>(
      "[data-user-menu-trigger]",
    );
    trigger?.click();
  }

  // Navigate backwards. If any v2 overlay (RDialog, RMenu, RDrawer, …)
  // is currently open we close the topmost one first — one B press
  // shouldn't both dismiss an overlay AND pop a history entry. With
  // nothing open it falls through to `router.back()`.
  //
  // Source of truth is the shared escape stack in
  // `lib/overlays/RDialog/escapeStack.ts` — every escapable surface
  // pushes itself there while open, so this check is Vuetify-free and
  // doesn't depend on any DOM marker class.
  function goBack() {
    if (hasOpenEscapable()) {
      closeTopEscapable();
      return;
    }
    router.back();
  }

  // Button-index → zero-argument action. Unlike BUTTON_MAP these don't
  // fire a repeat while held; one press = one action.
  const BUTTON_ACTIONS: Record<number, () => void> = {
    0: activateFocused, //          A / Cross — activate (navigate/click)
    1: goBack, //                   B / Circle — history back (or close modal)
    4: () => cycleSection(-1), //   LB / L1 — previous AppNav section
    5: () => cycleSection(1), //    RB / R1 — next AppNav section
    8: goBack, //                   Back / Share — same as B
    9: openUserMenu, //             Start / Options — open user menu
  };

  function install() {
    if (installed) return;
    if (typeof navigator === "undefined" || !navigator.getGamepads) return;
    installed = true;

    const states: Record<string, PadState> = {};
    const { setModality } = useInputModality();
    let rafId = 0;
    let everSawPad = false;

    const onAnyInput = () => setModality("pad");
    const onConnect = () => setModality("pad");
    window.addEventListener("gamepadconnected", onConnect);

    // Initial poll — if the browser already exposes a pad at install time
    // (Firefox, or Chrome on a reload where a pad was previously used),
    // flip modality immediately so the grid-nav autofocus can land without
    // waiting for a first press. Chrome hides pads until first interaction
    // for privacy; in that case this no-ops and the gamepadconnected event
    // or first button press takes over.
    function detectPadPresence() {
      const list = navigator.getGamepads?.() ?? [];
      const hasPad = Array.from(list).some((p) => isUsablePad(p));
      if (hasPad && !everSawPad) {
        everSawPad = true;
        setModality("pad");
      }
    }
    detectPadPresence();

    const loop = () => {
      const pads = navigator.getGamepads?.() ?? [];
      const t = performance.now();

      // Keep checking while no pad has been seen yet — covers the case
      // where a pad appears partway through the session (plugged in
      // mid-browse, or Chrome exposes it once the user moves a stick).
      if (!everSawPad) detectPadPresence();

      // While a game is running the emulator owns the pad directly —
      // translating presses into navigation here would, for example,
      // make B (or Circle / Nintendo-A, which share the standard B
      // index) quit the game. Suppress all built-in translation in that
      // case; the emulator reads `navigator.getGamepads()` itself.
      const gameOwnsInput = playingStore.playing;
      // On the controller-test screen the built-in actions are muted so
      // every button can be pressed and inspected without side effects.
      const actionsDisabled = ACTIONS_DISABLED_PATHS.has(route.path);

      for (const pad of pads) {
        // Skip disconnected phantom gamepads.
        if (!isUsablePad(pad)) continue;
        const key = `${pad.index}:${pad.id}`;
        const st = (states[key] ||= {
          buttons: {},
          axisNextAt: { x: 0, y: 0 },
        });

        // Left stick → ArrowKey equivalents.
        const x = pad.axes[0] ?? 0;
        const y = pad.axes[1] ?? 0;
        tickAxis(st, "x", x, t, (dir) => {
          if (gameOwnsInput) return;
          dispatchKey(
            dir < 0
              ? { key: "ArrowLeft", code: "ArrowLeft" }
              : { key: "ArrowRight", code: "ArrowRight" },
          );
        });
        tickAxis(st, "y", y, t, (dir) => {
          if (gameOwnsInput) return;
          dispatchKey(
            dir < 0
              ? { key: "ArrowUp", code: "ArrowUp" }
              : { key: "ArrowDown", code: "ArrowDown" },
          );
        });

        // Buttons. Three tracks, evaluated in order:
        //   * BUTTON_MAP → synthetic keyboard event, with repeat cadence.
        //   * BUTTON_ACTIONS → one-shot callback, fires on press edge only.
        //   * Always — emit a `gamepad:buttondown` CustomEvent so views
        //     can opt into per-button bindings without needing to touch
        //     useGamepad (e.g. the Player view subscribes to Y to flip
        //     the saves/states tab).
        // A button can be in any combination; press-edge always emits the
        // CustomEvent regardless of built-in semantics.
        for (let i = 0; i < pad.buttons.length; i++) {
          const button = pad.buttons[i];
          const binding = BUTTON_MAP[i];
          const action = BUTTON_ACTIONS[i];
          const prev = (st.buttons[i] ||= { pressed: false, nextRepeatAt: 0 });
          if (button.pressed) {
            if (!prev.pressed) {
              if (!gameOwnsInput) {
                if (binding) dispatchKey(binding);
                else if (!actionsDisabled) action?.();
                // Fire the CustomEvent on every press edge so views can
                // bind to buttons we don't otherwise reserve.
                window.dispatchEvent(
                  new CustomEvent("gamepad:buttondown", {
                    detail: { index: i, name: BUTTON_NAMES[i] },
                  }),
                );
              }
              onAnyInput();
              prev.pressed = true;
              prev.nextRepeatAt = t + INITIAL_DELAY_MS;
            } else if (!gameOwnsInput && binding && t >= prev.nextRepeatAt) {
              // Only synthetic-key bindings repeat while held.
              dispatchKey(binding);
              prev.nextRepeatAt = t + REPEAT_MS;
            }
          } else {
            prev.pressed = false;
            prev.nextRepeatAt = 0;
          }
        }
      }

      rafId = requestAnimationFrame(loop);
    };

    rafId = requestAnimationFrame(loop);

    onBeforeUnmount(() => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("gamepadconnected", onConnect);
      installed = false;
    });
  }

  return { install };
}

function tickAxis(
  st: PadState,
  axis: "x" | "y",
  value: number,
  now: number,
  fire: (direction: -1 | 1) => void,
) {
  if (Math.abs(value) < AXIS_THRESHOLD) {
    st.axisNextAt[axis] = 0;
    return;
  }
  const dir = value < 0 ? -1 : 1;
  if (st.axisNextAt[axis] === 0) {
    fire(dir);
    st.axisNextAt[axis] = now + INITIAL_DELAY_MS;
  } else if (now >= st.axisNextAt[axis]) {
    fire(dir);
    st.axisNextAt[axis] = now + REPEAT_MS;
  }
}
