import { defineConfig, devices } from "@playwright/test";
import { url as inspectorUrl } from "node:inspector";
import { REPORT_DIR, RESULTS_DIR } from "./e2e/support/output";

// End-to-end suite: `npm run test:e2e`. Variables come from the shell, then
// e2e/.env, which tools like the VS Code extension can't take from a terminal.
try {
  process.loadEnvFile(new URL("./e2e/.env", import.meta.url));
} catch (error) {
  if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
}
// Unset or empty, the config serves this checkout itself at SERVED_URL (see
// webServer).
const baseURL = process.env.E2E_BASE_URL || undefined;
const SERVED_PORT = 3000;
const SERVED_URL = `http://127.0.0.1:${SERVED_PORT}`;

const isCI = !!process.env.CI;
// Playwright lifts timeouts itself for `--debug` (PWDEBUG, where 0 or false
// means off), not for a debugger paused on a breakpoint.
const { PWDEBUG = "" } = process.env;
const debugging =
  !["", "0", "false"].includes(PWDEBUG) || inspectorUrl() !== undefined;
// 0 means no timeout.
const TIMEOUTS = debugging
  ? { test: 0, expect: 0, action: 0, navigation: 0 }
  : { test: 45_000, expect: 10_000, action: 15_000, navigation: 30_000 };

export default defineConfig({
  testDir: "./e2e/specs",
  outputDir: RESULTS_DIR,
  // Permission gating is global state on the server (the fixture users' grants),
  // so the specs read it rather than mutate it and are safe to parallelise.
  fullyParallel: true,
  forbidOnly: isCI,
  // Locally a failure shows on the first run; retries would hide it.
  retries: isCI ? 2 : 0,
  // Every worker hammers ONE server, so keep the pool small.
  workers: 2,
  // The HTML report holds each failure's trace: `npm run test:e2e:report`.
  reporter: [
    [isCI ? "github" : "list"],
    ["html", { outputFolder: REPORT_DIR, open: "never" }],
  ],
  // A test that genuinely needs longer calls `test.slow()`.
  timeout: TIMEOUTS.test,
  expect: { timeout: TIMEOUTS.expect },
  use: {
    ...devices["Desktop Chrome"],
    baseURL: baseURL ?? SERVED_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: TIMEOUTS.action,
    navigationTimeout: TIMEOUTS.navigation,
    // The PWA service worker precaches ~9MB on every fresh context, competing
    // with the first navigation. Nothing here tests offline support.
    serviceWorkers: "block",
    // The suite's theme is "auto" (see seedUiState), so this picks it.
    colorScheme: "dark",
  },
  projects: [
    // Signs each fixture user in and saves the session (auth.setup.ts); specs
    // pick one with `test.use({ storageState })`.
    {
      name: "setup",
      testDir: "./e2e/setup",
      testMatch: /\.setup\.ts$/,
      // A cold dev server can reload the page mid-sign-in.
      retries: 2,
    },
    {
      name: "chromium",
      dependencies: ["setup"],
    },
  ],
  // CI serves the static build, which never force-reloads mid-test as the dev
  // server does on a new dependency. Locally, the dev server is (re)used.
  ...(!baseURL && {
    webServer: {
      command: isCI
        ? `npm run build:preview && npm run preview -- --port ${SERVED_PORT} --strictPort --host 127.0.0.1`
        : "npm run dev",
      url: SERVED_URL,
      reuseExistingServer: !isCI,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  }),
});
