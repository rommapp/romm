import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { PAD_BUTTON } from "@/v2/composables/useGamepad";
import { useExitChord } from "./index";

const CHORD = [PAD_BUTTON.back, PAD_BUTTON.start];

function pad(
  held: number[],
  mapping: GamepadMappingType = "standard",
  connected = true,
) {
  return {
    mapping,
    connected,
    buttons: Array.from({ length: 17 }, (_, i) => ({
      pressed: held.includes(i),
    })),
  };
}

let pads: unknown[] = [];

beforeEach(() => {
  vi.useFakeTimers({
    toFake: ["setInterval", "clearInterval", "performance"],
  });
  pads = [];
  Object.defineProperty(navigator, "getGamepads", {
    value: () => pads,
    configurable: true,
  });
});

afterEach(() => {
  vi.useRealTimers();
});

function listen(active: () => boolean) {
  const onChord = vi.fn();
  const scope = effectScope();
  scope.run(() => useExitChord(active, onChord));
  return { onChord, scope };
}

describe("useExitChord", () => {
  it("fires once Select+Start has been held for the full hold", () => {
    const { onChord, scope } = listen(() => true);
    pads = [pad(CHORD)];

    vi.advanceTimersByTime(1400);
    expect(onChord).not.toHaveBeenCalled();
    vi.advanceTimersByTime(300);
    expect(onChord).toHaveBeenCalledTimes(1);
    scope.stop();
  });

  it("starts the hold over when either button is let go", () => {
    const { onChord, scope } = listen(() => true);
    pads = [pad(CHORD)];
    vi.advanceTimersByTime(1000);
    pads = [pad([PAD_BUTTON.back])];
    vi.advanceTimersByTime(200);
    pads = [pad(CHORD)];
    vi.advanceTimersByTime(1000);

    expect(onChord).not.toHaveBeenCalled();
    scope.stop();
  });

  it("ignores a disconnected pad's stale buttons", () => {
    // Firefox keeps disconnected entries in getGamepads() (#3851).
    const { onChord, scope } = listen(() => true);
    pads = [pad(CHORD, "standard", false)];

    vi.advanceTimersByTime(3000);

    expect(onChord).not.toHaveBeenCalled();
    scope.stop();
  });

  it("ignores pads without the standard mapping", () => {
    const { onChord, scope } = listen(() => true);
    pads = [pad(CHORD, "")];

    vi.advanceTimersByTime(3000);

    expect(onChord).not.toHaveBeenCalled();
    scope.stop();
  });

  it("only listens while the session is active", async () => {
    const active = ref(false);
    const { onChord, scope } = listen(() => active.value);
    pads = [pad(CHORD)];

    vi.advanceTimersByTime(3000);
    expect(onChord).not.toHaveBeenCalled();

    active.value = true;
    await nextTick();
    vi.advanceTimersByTime(1700);
    expect(onChord).toHaveBeenCalledTimes(1);
    scope.stop();
  });

  it("stops polling with its owning scope", () => {
    const { onChord, scope } = listen(() => true);
    scope.stop();
    pads = [pad(CHORD)];

    vi.advanceTimersByTime(3000);

    expect(onChord).not.toHaveBeenCalled();
  });
});
