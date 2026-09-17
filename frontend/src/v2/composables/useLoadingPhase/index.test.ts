import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { SKELETON_DELAY_MS, SKELETON_MIN_MS, useLoadingPhase } from "./index";

function setup(initial: { loading: boolean; empty: boolean }) {
  const loading = ref(initial.loading);
  const empty = ref(initial.empty);
  const scope = effectScope();
  const phase = scope.run(() => useLoadingPhase(loading, empty))!;
  return { loading, empty, phase, scope };
}

describe("useLoadingPhase", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("settles on content straight away", () => {
    const { phase } = setup({ loading: false, empty: false });

    expect(phase.value).toBe("content");
  });

  it("waits a tick before settling on empty, so a fetch started on mount wins", async () => {
    const { loading, phase } = setup({ loading: false, empty: true });
    expect(phase.value).toBe("idle");

    loading.value = true;
    await nextTick();

    expect(phase.value).toBe("idle");
  });

  it("skips the skeleton when the load beats the delay", async () => {
    const { loading, empty, phase } = setup({ loading: true, empty: true });

    await vi.advanceTimersByTimeAsync(SKELETON_DELAY_MS - 1);
    expect(phase.value).toBe("idle");

    empty.value = false;
    loading.value = false;
    await nextTick();

    expect(phase.value).toBe("content");
  });

  it("shows the skeleton once the load outlasts the delay", async () => {
    const { phase } = setup({ loading: true, empty: true });

    await vi.advanceTimersByTimeAsync(SKELETON_DELAY_MS);

    expect(phase.value).toBe("skeleton");
  });

  it("keeps a painted skeleton up for its minimum before settling", async () => {
    const { loading, phase } = setup({ loading: true, empty: true });
    await vi.advanceTimersByTimeAsync(SKELETON_DELAY_MS);

    loading.value = false;
    await vi.advanceTimersByTimeAsync(SKELETON_MIN_MS - 1);
    expect(phase.value).toBe("skeleton");

    await vi.advanceTimersByTimeAsync(1);
    expect(phase.value).toBe("empty");
  });

  it("holds the settled phase through a quick refetch", async () => {
    const { loading, empty, phase } = setup({ loading: false, empty: true });
    await vi.advanceTimersByTimeAsync(0);
    expect(phase.value).toBe("empty");

    loading.value = true;
    await vi.advanceTimersByTimeAsync(SKELETON_DELAY_MS - 1);
    expect(phase.value).toBe("empty");

    empty.value = false;
    loading.value = false;
    await nextTick();

    expect(phase.value).toBe("content");
  });
});
