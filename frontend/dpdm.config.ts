import { defineConfig } from "dpdm";

export default defineConfig({
  files: [
    // Production app bootstrap (router, plugins, stores).
    "src/main.ts",
    // API client hub; catches api ↔ router ↔ rom static cycles.
    "src/services/api/index.ts",
    // Every Storybook story file; covers import paths Vitest does not run.
    "src/**/*.stories.ts",
    // Shared Storybook runtime (Pinia, i18n, permissions seed), not main.ts.
    ".storybook/preview.ts",
  ],
  circular: true,
  tree: false,
  warning: false,
  exitCode: "circular:1",
  transform: true,
});
