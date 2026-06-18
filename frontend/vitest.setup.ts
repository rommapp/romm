import { setProjectAnnotations } from "@storybook/vue3-vite";
import * as previewAnnotations from "./.storybook/preview";

setProjectAnnotations([
  previewAnnotations as Parameters<typeof setProjectAnnotations>[0][number],
]);
