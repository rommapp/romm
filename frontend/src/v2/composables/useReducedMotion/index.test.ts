import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

const KEY = "settings.v2.reducedMotion";

// A minimal in-memory Storage. The hook reads `window.localStorage` (via
// vueuse), which under this env + Node isn't reliably wired up for a pure,
// non-DOM test file, so we install our own and assert against it.
function makeStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key) => (map.has(key) ? (map.get(key) as string) : null),
    setItem: (key, value) => void map.set(key, String(value)),
    removeItem: (key) => void map.delete(key),
    key: (index) => [...map.keys()][index] ?? null,
  };
}
let store: Storage;

// Force the OS `prefers-reduced-motion` result the next fresh import will read.
function stubReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// `override` / `systemPreference` / `enabled` are module-level singletons
// created at import time, so they read localStorage + matchMedia exactly once
// on load. Re-import fresh after seeding both to exercise the default /
// override paths in isolation.
async function loadFresh() {
  vi.resetModules();
  const { useReducedMotion } = await import("./index");
  return useReducedMotion();
}

const realMatchMedia = window.matchMedia;

beforeEach(() => {
  store = makeStorage();
  vi.stubGlobal("localStorage", store);
  Object.defineProperty(window, "localStorage", {
    value: store,
    configurable: true,
    writable: true,
  });
  stubReducedMotion(false);
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.matchMedia = realMatchMedia;
});

describe("useReducedMotion", () => {
  it("defaults to the system prefers-reduced-motion setting when unset", async () => {
    stubReducedMotion(true);
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(true);
  });

  it("defaults to off when the system has no reduced-motion preference", async () => {
    stubReducedMotion(false);
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(false);
  });

  it("an explicit 'off' override wins over a system reduced-motion preference", async () => {
    stubReducedMotion(true);
    store.setItem(KEY, "false");
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(false);
  });

  it("restores an explicit 'on' override regardless of the system setting", async () => {
    stubReducedMotion(false);
    store.setItem(KEY, "true");
    const { enabled } = await loadFresh();
    expect(enabled.value).toBe(true);
  });

  it("toggle() records an explicit override under the settings key", async () => {
    const { enabled, toggle } = await loadFresh();
    expect(enabled.value).toBe(false);

    expect(toggle()).toBe(true);
    expect(enabled.value).toBe(true);
    await nextTick();
    expect(store.getItem(KEY)).toBe("true");
  });

  it("toggle() from a system-on default writes an explicit off", async () => {
    stubReducedMotion(true);
    const { enabled, toggle } = await loadFresh();
    expect(enabled.value).toBe(true);

    expect(toggle()).toBe(false);
    await nextTick();
    expect(store.getItem(KEY)).toBe("false");
  });

  it("shares a single instance across calls within a load", async () => {
    vi.resetModules();
    const { useReducedMotion } = await import("./index");
    const a = useReducedMotion();
    const b = useReducedMotion();
    a.toggle();
    expect(b.enabled.value).toBe(true);
  });
});
