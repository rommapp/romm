import { flushPromises } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { expectNoUnhandledRejection } from "@/test-utils/unhandledRejection";
import {
  skippedReady,
  stubStartViewTransition,
} from "@/test-utils/viewTransition";
import {
  installBackMorph,
  isMorphRunning,
  pendingMorphName,
  useViewTransition,
} from "./index";

vi.mock("@/plugins/router", () => ({
  ROUTES: {
    ROM: "rom",
    EMULATORJS: "emulatorjs",
    JSDOS: "jsdos",
    PICO8: "pico8",
    RUFFLE: "ruffle",
  },
}));

vi.mock("@/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: { value: false } }),
}));

afterEach(() => {
  Reflect.deleteProperty(document, "startViewTransition");
});

// A real router on memory history, so the guard runs against the route
// objects it would see in the app.
function routerWithBackMorph() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/platform/:platform",
        name: "platform",
        component: { render: () => null },
      },
      { path: "/rom/:rom", name: "rom", component: { render: () => null } },
    ],
  });
  installBackMorph(router);
  return router;
}

describe("morphTransition", () => {
  it("absorbs the skip the router's own transition causes", async () => {
    await expectNoUnhandledRejection(() => {
      void stubStartViewTransition(skippedReady());
      const { morphTransition } = useViewTransition();

      morphTransition(
        { el: document.createElement("div"), name: "rom-cover-1" },
        () => {},
      );
      return Promise.resolve();
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
    await flushPromises();

    expect(el.style.viewTransitionName).toBe("");
    el.remove();
  });
});

describe("isMorphRunning", () => {
  it("is true while a forward morph or a back-morph tag is live", async () => {
    let finish!: () => void;
    const finished = new Promise<void>((r) => {
      finish = r;
    });
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      value: vi.fn((callback?: () => Promise<void>) => {
        void callback?.();
        return {
          updateCallbackDone: Promise.resolve(),
          ready: Promise.resolve(),
          finished,
          skipTransition: () => {},
        };
      }),
    });
    const { morphTransition } = useViewTransition();
    expect(isMorphRunning()).toBe(false);

    morphTransition(
      { el: document.createElement("div"), name: "rom-cover-1" },
      () => {},
    );
    expect(isMorphRunning()).toBe(true);
    finish();
    await flushPromises();
    expect(isMorphRunning()).toBe(false);

    pendingMorphName.value = "rom-cover-2";
    expect(isMorphRunning()).toBe(true);
    pendingMorphName.value = null;
  });
});

describe("installBackMorph", () => {
  it("absorbs the skip a navigation during capture causes", async () => {
    await expectNoUnhandledRejection(async () => {
      void stubStartViewTransition(skippedReady());
      const router = routerWithBackMorph();

      await router.push("/platform/2");
      await router.push("/rom/18");
    });
  });
});
