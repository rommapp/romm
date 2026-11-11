import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { throttle } from "./throttle";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("throttle", () => {
  it("fires on the leading edge and once more with the latest args", () => {
    const fn = vi.fn();
    const t = throttle(fn, 200);
    t(1);
    t(2);
    t(3);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenLastCalledWith(1);
    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith(3);
  });

  it("fires again immediately after a quiet period", () => {
    const fn = vi.fn();
    const t = throttle(fn, 200);
    t(1);
    vi.advanceTimersByTime(300);
    t(2);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("cancel drops the trailing call", () => {
    const fn = vi.fn();
    const t = throttle(fn, 200);
    t(1);
    t(2);
    t.cancel();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
