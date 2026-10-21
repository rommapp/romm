import { beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";

const reduced = ref(false);
vi.mock("@/v2/composables/useReducedMotion", () => ({
  useReducedMotion: () => ({ enabled: reduced }),
}));

const { pickOther, useArtworkCycle } = await import("./index");

const IDS = ["aurora", "ember", "neon"];

describe("useArtworkCycle", () => {
  let visibility: DocumentVisibilityState = "visible";

  async function show(state: DocumentVisibilityState) {
    visibility = state;
    document.dispatchEvent(new Event("visibilitychange"));
    await nextTick();
  }

  // Lets the awaited preload settle after a timer tick.
  async function flush() {
    await Promise.resolve();
    await Promise.resolve();
    await nextTick();
  }

  beforeEach(() => {
    visibility = "visible";
    reduced.value = false;
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    vi.spyOn(document, "visibilityState", "get").mockImplementation(
      () => visibility,
    );
  });

  function setup(ids = ref(IDS), preload = vi.fn(() => Promise.resolve())) {
    const scope = effectScope();
    const cycle = scope.run(() => useArtworkCycle(ids, 2000, { preload }))!;
    return { ...cycle, preload, scope, ids };
  }

  it("switches to a different pack every interval, after preloading it", async () => {
    const { current, preload } = setup();
    const seen = [current.value];

    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(2000);
      await flush();
      expect(current.value).not.toBe(seen.at(-1));
      expect(preload).toHaveBeenLastCalledWith(current.value);
      seen.push(current.value);
    }
    expect(IDS).toEqual(expect.arrayContaining(seen));
  });

  it("does not switch until the next pack's images have loaded", async () => {
    let finish = () => {};
    const preload = vi.fn(
      () => new Promise<void>((resolve) => (finish = resolve)),
    );
    const { current } = setup(ref(IDS), preload);
    const first = current.value;

    vi.advanceTimersByTime(4000);
    await flush();
    expect(current.value).toBe(first);
    expect(preload).toHaveBeenCalledOnce();

    finish();
    await flush();
    expect(current.value).not.toBe(first);
  });

  it("pauses while the tab is hidden and resumes when shown", async () => {
    const { current, cycling, preload } = setup();
    const first = current.value;
    await show("hidden");
    expect(cycling.value).toBe(false);

    vi.advanceTimersByTime(6000);
    await flush();
    expect(preload).not.toHaveBeenCalled();
    expect(current.value).toBe(first);

    await show("visible");
    vi.advanceTimersByTime(2000);
    await flush();
    expect(current.value).not.toBe(first);
  });

  it("holds one pack with reduced motion on", async () => {
    reduced.value = true;
    const { current, cycling, preload } = setup();
    const first = current.value;
    expect(first).not.toBeNull();
    expect(cycling.value).toBe(false);

    vi.advanceTimersByTime(10000);
    await flush();
    expect(preload).not.toHaveBeenCalled();
    expect(current.value).toBe(first);
  });

  it("shows a single pack without cycling, and nothing when there are none", async () => {
    const ids = ref(["ember"]);
    const { current, cycling, preload } = setup(ids);
    expect(current.value).toBe("ember");
    expect(cycling.value).toBe(false);
    vi.advanceTimersByTime(6000);
    expect(preload).not.toHaveBeenCalled();

    ids.value = [];
    await nextTick();
    expect(current.value).toBeNull();
  });

  it("pickOther never repeats the current id when it has a choice", () => {
    for (let r = 0; r < 1; r += 0.05) {
      expect(pickOther(IDS, "ember", () => r)).not.toBe("ember");
    }
    expect(pickOther(["ember"], "ember")).toBe("ember");
    expect(pickOther([], null)).toBeNull();
  });
});
