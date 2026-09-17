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
  it("invokes the callback once when the native API is available", async () => {
    stubNativeTransition(Promise.resolve());
    const callback = vi.fn(async () => {});

    const transition = startViewTransition(callback);
    await transition.captured;

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("invokes the callback once when a native transition is preempted", async () => {
    stubNativeTransition(Promise.reject(skipped()));
    const callback = vi.fn(async () => {});

    const transition = startViewTransition(callback);
    await transition.ready.catch(() => {});

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("invokes the callback once and resolves its promises without the native API", async () => {
    const callback = vi.fn(async () => {});

    const transition = startViewTransition(callback);

    await expect(transition.captured).resolves.toBeUndefined();
    await expect(transition.updateCallbackDone).resolves.toBeUndefined();
    await expect(transition.ready).resolves.toBeUndefined();
    await expect(transition.finished).resolves.toBeUndefined();
    expect(callback).toHaveBeenCalledTimes(1);
  });
});
