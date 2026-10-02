import { setProjectAnnotations } from "@storybook/vue3-vite";
import { enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, vi } from "vitest";
import * as previewAnnotations from "./.storybook/preview";

// After-hooks run in reverse, so this lands after auto-unmount clears its timers.
afterEach(() => {
  vi.useRealTimers();
});

// A mount left standing keeps its window listeners and timers, which would
// answer the next test's events.
enableAutoUnmount(afterEach);

// Every test starts with empty stores; a test that needs its own Pinia sets it.
beforeEach(() => setActivePinia(createPinia()));

setProjectAnnotations([
  previewAnnotations as Parameters<typeof setProjectAnnotations>[0][number],
]);
