import { beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick } from "vue";
import { useVisiblePoll } from "./index";

describe("useVisiblePoll", () => {
  let visibility: DocumentVisibilityState = "visible";

  async function show(state: DocumentVisibilityState) {
    visibility = state;
    document.dispatchEvent(new Event("visibilitychange"));
    await nextTick();
  }

  beforeEach(() => {
    visibility = "visible";
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    vi.spyOn(document, "visibilityState", "get").mockImplementation(
      () => visibility,
    );
  });

  function setup(options?: { immediate?: boolean }) {
    const fn = vi.fn();
    const scope = effectScope();
    const poll = scope.run(() => useVisiblePoll(fn, 1000, options))!;
    return { fn, scope, poll };
  }

  it("calls on every interval while the tab is visible", () => {
    const { fn } = setup();

    vi.advanceTimersByTime(3000);

    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("skips ticks while hidden and catches up once shown", async () => {
    const { fn } = setup();
    await show("hidden");

    vi.advanceTimersByTime(3000);
    expect(fn).not.toHaveBeenCalled();

    await show("visible");
    expect(fn).toHaveBeenCalledOnce();
  });

  it("stays quiet on return while paused", async () => {
    const { fn, poll } = setup({ immediate: false });
    await show("hidden");

    await show("visible");
    vi.advanceTimersByTime(3000);
    expect(fn).not.toHaveBeenCalled();

    poll.resume();
    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledOnce();
  });

  it("stops once its scope is disposed", async () => {
    const { fn, scope } = setup();
    await show("hidden");

    scope.stop();
    await show("visible");
    vi.advanceTimersByTime(3000);

    expect(fn).not.toHaveBeenCalled();
  });
});
