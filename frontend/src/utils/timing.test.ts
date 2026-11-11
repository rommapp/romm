import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { debounce, throttle } from "./timing";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("debounce", () => {
  it("runs once after the last call with its arguments", () => {
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d(1);
    vi.advanceTimersByTime(60);
    d(2);
    vi.advanceTimersByTime(99);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledOnce();
    expect(fn).toHaveBeenCalledWith(2);
  });

  it("cancel drops the pending call", () => {
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d();
    d.cancel();
    vi.advanceTimersByTime(500);
    expect(fn).not.toHaveBeenCalled();
  });

  it("flush runs the pending call now, once", () => {
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d();
    d.flush();
    expect(fn).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledOnce();
  });

  it("flush with nothing pending does nothing", () => {
    const fn = vi.fn();
    debounce(fn, 100).flush();
    expect(fn).not.toHaveBeenCalled();
  });

  it("maxWait fires during a steady stream of calls", () => {
    const fn = vi.fn();
    const d = debounce(fn, 100, { maxWait: 250 });
    for (let i = 0; i < 6; i++) {
      d();
      vi.advanceTimersByTime(60);
    }
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

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
