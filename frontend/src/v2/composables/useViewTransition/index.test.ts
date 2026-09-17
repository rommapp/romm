import { afterEach, describe, expect, it, vi } from "vitest";
import type { RouteLocationNormalized, Router } from "vue-router";
import { expectNoUnhandledRejection } from "@/test-utils/unhandledRejection";
import {
  skippedReady,
  stubStartViewTransition,
} from "@/test-utils/viewTransition";
import { installBackMorph, useViewTransition } from "./index";

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

afterEach(() => {
  Reflect.deleteProperty(document, "startViewTransition");
});

// Keeps the guard installBackMorph registers, so a navigation can be replayed
// through it without a real router.
function captureBackMorphGuard() {
  const guards: Array<
    (to: RouteLocationNormalized, from: RouteLocationNormalized) => unknown
  > = [];
  installBackMorph({
    beforeResolve: (guard: never) => {
      guards.push(guard);
      return () => {};
    },
  } as unknown as Router);
  return guards[0];
}

describe("morphTransition", () => {
  it("absorbs the skip the router's own transition causes", async () => {
    await expectNoUnhandledRejection(async () => {
      stubStartViewTransition(skippedReady());
      const { morphTransition } = useViewTransition();

      morphTransition(
        { el: document.createElement("div"), name: "rom-cover-1" },
        () => {},
      );
    });
  });

  it("clears the morph tag once the transition finishes", async () => {
    const finished = stubStartViewTransition(Promise.resolve());
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

describe("installBackMorph", () => {
  it("absorbs the skip a navigation during capture causes", async () => {
    await expectNoUnhandledRejection(async () => {
      stubStartViewTransition(skippedReady());
      const guard = captureBackMorphGuard();
      const romRoute = { name: "rom", params: { rom: "18" } };
      const platformRoute = { name: "platform", params: { platform: "2" } };

      await guard(
        platformRoute as unknown as RouteLocationNormalized,
        romRoute as unknown as RouteLocationNormalized,
      );
    });
  });
});
