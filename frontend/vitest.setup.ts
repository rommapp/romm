import { setProjectAnnotations } from "@storybook/vue3-vite";
import { enableAutoUnmount } from "@vue/test-utils";
import { afterEach } from "vitest";
import * as previewAnnotations from "./.storybook/preview";

// A mount left standing keeps its window listeners and timers, which would
// answer the next test's events.
enableAutoUnmount(afterEach);

setProjectAnnotations([
  previewAnnotations as Parameters<typeof setProjectAnnotations>[0][number],
]);
