import { config, enableAutoUnmount } from "@vue/test-utils";
import mitt from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, vi } from "vitest";
// Loaded here, before any test file mocks vue-i18n (see __mocks__/vue-i18n.ts),
// so the shared i18n instance is built from the real library.
import "@/locales";
import { stopScopes } from "@/test-utils/effectScope";

// The Cache API is missing from the test DOM, so the cache service falls back to memory
// and says so on import. That is the path every test wants.
const CACHE_FALLBACK_NOTICE =
  "Cache API not supported, falling back to memory cache";
const warn = console.warn.bind(console);
console.warn = (...args: unknown[]) => {
  if (args[0] !== CACHE_FALLBACK_NOTICE) warn(...args);
};

// Components inject the app-wide event bus. A test that asserts on it provides its
// own, which wins over this default.
const emitter = mitt();
config.global.provide = { ...config.global.provide, emitter };
afterEach(() => {
  emitter.all.clear();
  stopScopes();
});

// After-hooks run in reverse, so this lands after auto-unmount clears its timers.
afterEach(() => {
  vi.useRealTimers();
});

// A mount left standing keeps its window listeners and timers, which would
// answer the next test's events.
enableAutoUnmount(afterEach);

// Every test starts with empty stores; a test that needs its own Pinia sets it.
beforeEach(() => setActivePinia(createPinia()));
