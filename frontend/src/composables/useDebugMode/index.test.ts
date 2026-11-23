import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const KEY = "settings.v2.debugMode";

// `enabled` is a module-level singleton created at import time, so it reads
// localStorage exactly once on load. Re-import the module fresh after seeding
// storage to exercise the default / persisted-read paths in isolation.
async function loadFresh() {
  vi.resetModules();
  const { useDebugMode } = await import("./index");
  return useDebugMode();
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("useDebugMode", () => {
  it("defaults to off when nothing is persisted", async () => {
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(false);
  });

  it("restores a previously persisted value on load", async () => {
    localStorage.setItem(KEY, "true");
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(true);
  });

  it("persists changes under the 'settings.v2.debugMode' key", async () => {
    const { enabled } = await loadFresh();
    enabled.value = true;
    await nextTick();
    expect(localStorage.getItem(KEY)).toBe("true");
  });

  it("shares a single instance across calls within a load", async () => {
    vi.resetModules();
    const { useDebugMode } = await import("./index");
    const a = useDebugMode();
    const b = useDebugMode();
    a.enabled.value = true;
    expect(b.enabled.value).toBe(true);
  });
});
