import { setProjectAnnotations } from "@storybook/vue3-vite";
import { enableAutoUnmount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach } from "vitest";
import * as previewAnnotations from "./.storybook/preview";

// A mount left standing keeps its window listeners and timers, which would
// answer the next test's events.
enableAutoUnmount(afterEach);

// Every test starts with empty stores; a test that needs its own Pinia sets it.
beforeEach(() => setActivePinia(createPinia()));

setProjectAnnotations([
  previewAnnotations as Parameters<typeof setProjectAnnotations>[0][number],
]);
