import { afterEach, describe, expect, it, vi } from "vitest";
import { useViewTransition } from "./index";

vi.mock("@/plugins/router", () => ({
  ROUTES: {
    ROM: "rom",
    EMULATORJS: "emulatorjs",
    JSDOS: "jsdos",
    PICO8: "pico8",
    RUFFLE: "ruffle",
  },
}));

vi.mock("@/v2/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: { value: false } }),
}));

// happy-dom has no View Transitions API, so the native call is always stubbed.
// The stub runs the update callback, as the browser does even when it skips.
function stubNativeTransition(ready: Promise<void>) {
  const finished = Promise.resolve();
  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    value: vi.fn((callback?: () => Promise<void>) => {
      void callback?.();
      return {
        updateCallbackDone: Promise.resolve(),
        ready,
        finished,
        skipTransition: () => {},
      };
    }),
  });
  return finished;
}

afterEach(() => {
  Reflect.deleteProperty(document, "startViewTransition");
});

describe("morphTransition", () => {
  it("absorbs the skip the router's own transition causes", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    try {
      stubNativeTransition(
        Promise.reject(
          new DOMException("Transition was skipped", "AbortError"),
        ),
      );
      const { morphTransition } = useViewTransition();

      morphTransition(
        { el: document.createElement("div"), name: "rom-cover-1" },
        () => {},
      );
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(unhandled).not.toHaveBeenCalled();
    } finally {
      process.off("unhandledRejection", unhandled);
    }
  });

  it("clears the morph tag once the transition finishes", async () => {
    const finished = stubNativeTransition(Promise.resolve());
    const el = document.createElement("div");
    document.body.appendChild(el);
    const { morphTransition } = useViewTransition();

    morphTransition({ el, name: "rom-cover-1" }, () => {});
    expect(el.style.viewTransitionName).toBe("rom-cover-1");
    await finished;
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(el.style.viewTransitionName).toBe("");
    el.remove();
  });
});
