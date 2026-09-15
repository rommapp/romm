import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import storePlaying from "@/stores/playing";
import { installStageActiveClass, useStageActive } from "./index";

beforeEach(() => {
  setActivePinia(createPinia());
  document.documentElement.classList.remove("r-v2-stage-active");
});

describe("useStageActive", () => {
  it("mirrors the running source into the store flag", async () => {
    const running = ref(false);
    const scope = effectScope();
    scope.run(() => useStageActive(running));
    const store = storePlaying();
    expect(store.stageActive).toBe(false);

    running.value = true;
    await nextTick();
    expect(store.stageActive).toBe(true);

    running.value = false;
    await nextTick();
    expect(store.stageActive).toBe(false);
    scope.stop();
  });

  it("clears the flag when its owning scope is disposed", () => {
    const running = ref(true);
    const scope = effectScope();
    scope.run(() => useStageActive(running));
    const store = storePlaying();
    expect(store.stageActive).toBe(true);

    scope.stop();
    expect(store.stageActive).toBe(false);
  });

  it("stays independent of the playing flag", () => {
    const scope = effectScope();
    scope.run(() => useStageActive(() => false));
    const store = storePlaying();

    // Stream sets `playing` while still on its config screen.
    store.setPlaying(true);
    expect(store.stageActive).toBe(false);
    scope.stop();
  });
});

describe("installStageActiveClass", () => {
  function htmlHasClass(): boolean {
    return document.documentElement.classList.contains("r-v2-stage-active");
  }

  it("mirrors the flag onto <html> in both directions", async () => {
    const scope = effectScope();
    scope.run(() => installStageActiveClass());
    const store = storePlaying();
    expect(htmlHasClass()).toBe(false);

    store.setStageActive(true);
    await nextTick();
    expect(htmlHasClass()).toBe(true);

    store.setStageActive(false);
    await nextTick();
    expect(htmlHasClass()).toBe(false);
    scope.stop();
  });

  it("removes the class when its owning scope is disposed", async () => {
    const scope = effectScope();
    scope.run(() => installStageActiveClass());
    const store = storePlaying();
    store.setStageActive(true);
    await nextTick();
    expect(htmlHasClass()).toBe(true);

    scope.stop();
    expect(htmlHasClass()).toBe(false);
  });
});
