import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import { usePlayFocus } from "./index";

const { setModality } = useInputModality();

describe("usePlayFocus", () => {
  let play: HTMLButtonElement;
  let elsewhere: HTMLButtonElement;
  let scope: ReturnType<typeof effectScope> | null = null;

  const ready = ref(false);
  const running = ref(false);

  // Two ticks: one for the watcher's flush, one for the nextTick it defers
  // the focus call to.
  async function settle() {
    await nextTick();
    await nextTick();
  }

  function run() {
    scope = effectScope();
    scope.run(() => usePlayFocus(".play", ready, running));
  }

  beforeEach(() => {
    play = document.createElement("button");
    play.className = "play";
    elsewhere = document.createElement("button");
    document.body.append(play, elsewhere);
    ready.value = false;
    running.value = false;
    setModality("mouse");
  });

  afterEach(() => {
    scope?.stop();
    scope = null;
    play.remove();
    elsewhere.remove();
  });

  it("claims the CTA once the screen is ready on a pad", async () => {
    setModality("pad");
    run();

    ready.value = true;
    await settle();

    expect(document.activeElement).toBe(play);
  });

  it("claims it when a mouse user picks up a pad", async () => {
    run();
    ready.value = true;
    await settle();
    expect(document.activeElement).not.toBe(play);

    setModality("pad");
    await settle();

    expect(document.activeElement).toBe(play);
  });

  it("leaves a focused element alone", async () => {
    run();
    ready.value = true;
    elsewhere.focus();

    setModality("pad");
    await settle();

    expect(document.activeElement).toBe(elsewhere);
  });

  it("stays off the CTA while the game is running", async () => {
    setModality("pad");
    run();

    ready.value = true;
    running.value = true;
    await settle();

    expect(document.activeElement).not.toBe(play);
  });

  it("lands back on the CTA when the game exits", async () => {
    setModality("mouse");
    ready.value = true;
    running.value = true;
    run();

    running.value = false;
    await settle();

    expect(document.activeElement).toBe(play);
  });
});
