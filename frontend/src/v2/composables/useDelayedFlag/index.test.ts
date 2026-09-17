import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useDelayedFlag } from "./index";

describe("useDelayedFlag", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("turns on only once the source has stayed on for the delay", async () => {
    const source = ref(true);
    const flag = effectScope().run(() => useDelayedFlag(source, 200))!;

    await vi.advanceTimersByTimeAsync(199);
    expect(flag.value).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    expect(flag.value).toBe(true);
  });

  it("turns off at once and drops a pending turn-on", async () => {
    const source = ref(true);
    const flag = effectScope().run(() => useDelayedFlag(source, 200))!;

    await vi.advanceTimersByTimeAsync(100);
    source.value = false;
    await nextTick();
    await vi.advanceTimersByTimeAsync(200);

    expect(flag.value).toBe(false);
  });

  it("follows the source immediately with no delay", async () => {
    const source = ref(false);
    const flag = effectScope().run(() => useDelayedFlag(source, 0))!;

    source.value = true;
    await nextTick();

    expect(flag.value).toBe(true);
  });
});
