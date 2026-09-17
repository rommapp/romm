import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoUnhandledRejection } from "@/test-utils/unhandledRejection";
import {
  skippedReady,
  stubStartViewTransition,
} from "@/test-utils/viewTransition";
import { startViewTransition } from "./index";

afterEach(() => {
  Reflect.deleteProperty(document, "startViewTransition");
});

describe("startViewTransition", () => {
  it("invokes the callback once when the native API is available", async () => {
    stubStartViewTransition(Promise.resolve());
    const callback = vi.fn(async () => {});

    const transition = startViewTransition(callback);
    await transition.captured;

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it("invokes the callback once when a native transition is preempted", async () => {
    stubStartViewTransition(skippedReady());
    const callback = vi.fn(async () => {});

    const transition = startViewTransition(callback);
    await transition.ready;

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

  it("resolves ready when the browser skips a preempted transition", async () => {
    stubStartViewTransition(skippedReady());

    await expect(startViewTransition().ready).resolves.toBeUndefined();
  });

  it("keeps a ready failure that is not a preemption skip", async () => {
    stubStartViewTransition(
      Promise.reject(new Error("navigation setup failed")),
    );

    await expect(startViewTransition().ready).rejects.toThrow(
      "navigation setup failed",
    );
  });

  it("leaves no unhandled rejection behind when a transition is preempted", async () => {
    await expectNoUnhandledRejection(async () => {
      stubStartViewTransition(skippedReady());

      const transition = startViewTransition();
      await transition.captured;
    });
  });
});
