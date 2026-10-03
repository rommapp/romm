import { enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, vi } from "vitest";
// Loaded here, before any test file mocks vue-i18n (see __mocks__/vue-i18n.ts),
// so the shared i18n instance is built from the real library.
import "@/locales";

// After-hooks run in reverse, so this lands after auto-unmount clears its timers.
afterEach(() => {
  vi.useRealTimers();
});

// A mount left standing keeps its window listeners and timers, which would
// answer the next test's events.
enableAutoUnmount(afterEach);

// Every test starts with empty stores; a test that needs its own Pinia sets it.
beforeEach(() => setActivePinia(createPinia()));
