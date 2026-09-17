import { afterEach, describe, expect, it, vi } from "vitest";
import { startViewTransition } from "./index";

const skipped = () => new DOMException("Transition was skipped", "AbortError");

// happy-dom has no View Transitions API, so the native call is always stubbed.
// The stub runs the update callback, as the browser does even when it skips.
function stubNativeTransition(ready: Promise<void>) {
  Object.defineProperty(document, "startViewTransition", {
    configurable: true,
    value: vi.fn((callback?: () => Promise<void>) => {
      void callback?.();
      return {
        updateCallbackDone: Promise.resolve(),
        ready,
        finished: Promise.resolve(),
        skipTransition: () => {},
      };
    }),
  });
}

afterEach(() => {
  Reflect.deleteProperty(document, "startViewTransition");
});

describe("startViewTransition", () => {
  it("resolves ready when the browser skips a preempted transition", async () => {
    stubNativeTransition(Promise.reject(skipped()));

    await expect(startViewTransition().ready).resolves.toBeUndefined();
  });

  it("leaves no unhandled rejection behind when a transition is preempted", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    try {
      stubNativeTransition(Promise.reject(skipped()));

      const transition = startViewTransition();
      await transition.captured;
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(unhandled).not.toHaveBeenCalled();
    } finally {
      process.off("unhandledRejection", unhandled);
    }
  });
});
