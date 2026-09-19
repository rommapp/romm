import { defineConfig } from "dpdm";

export default defineConfig({
  files: [
    "src/main.ts",
    "src/services/api/index.ts",
    "src/**/*.stories.ts",
    ".storybook/preview.ts",
  ],
  circular: true,
  tree: false,
  warning: false,
  exitCode: "circular:1",
  transform: true,
});
