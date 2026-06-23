import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const KEY = "settings.v2.crtMode";

// `enabled` is a module-level singleton created at import time, so it reads
// localStorage exactly once on load. Re-import the module fresh after seeding
// storage to exercise the default / persisted-read paths in isolation.
async function loadFresh() {
  vi.resetModules();
  const { useCrtMode } = await import("./index");
  return useCrtMode();
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("useCrtMode", () => {
  it("defaults to off when nothing is persisted", async () => {
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(false);
  });

  it("restores a previously persisted value on load", async () => {
    localStorage.setItem(KEY, "true");
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(true);
  });

  it("persists changes under the 'settings.v2.crtMode' key", async () => {
    const { enabled } = await loadFresh();
    enabled.value = true;
    await nextTick();
    expect(localStorage.getItem(KEY)).toBe("true");
  });

  it("toggle() flips the state and returns the new value", async () => {
    const { enabled, toggle } = await loadFresh();
    expect(enabled.value).toBe(false);

    expect(toggle()).toBe(true);
    expect(enabled.value).toBe(true);

    expect(toggle()).toBe(false);
    expect(enabled.value).toBe(false);
  });

  it("toggle() writes through to localStorage", async () => {
    const { toggle } = await loadFresh();
    toggle();
    await nextTick();
    expect(localStorage.getItem(KEY)).toBe("true");
  });

  it("shares a single instance across calls within a load", async () => {
    vi.resetModules();
    const { useCrtMode } = await import("./index");
    const a = useCrtMode();
    const b = useCrtMode();
    a.toggle();
    expect(b.enabled.value).toBe(true);
  });
});
