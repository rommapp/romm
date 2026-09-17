import { afterEach, describe, expect, it } from "vitest";
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
