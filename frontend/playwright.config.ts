import { defineConfig, devices } from "@playwright/test";
import { url as inspectorUrl } from "node:inspector";
import { readE2EEnv } from "./e2e/support/e2e-environment";
import { suiteOutput } from "./e2e/support/output";
import type { E2EOptions } from "./e2e/support/test";

// End-to-end suite: `npm run test:e2e`. Without E2E_BASE_URL it serves the app
// itself; see e2e/.env.example.
const env = readE2EEnv();
const output = suiteOutput("specs");

const isCI = env.CI;
// A test paused on a breakpoint must not be killed by the timeouts below.
const debugging = !!process.env.PWDEBUG || inspectorUrl() !== undefined;
// Local runs fail fast; CI allows for a slower shared runner. 0 means no
// timeout.
const TIMEOUTS = debugging
  ? { test: 0, expect: 0, action: 0, navigation: 0 }
  : isCI
    ? { test: 45_000, expect: 10_000, action: 15_000, navigation: 30_000 }
    : { test: 10_000, expect: 3_000, action: 5_000, navigation: 5_000 };

export default defineConfig<E2EOptions>({
  testDir: "./e2e/specs",
  outputDir: output.results,
  // Permission gating is global state on the server (the fixture users' grants),
  // so the specs read it rather than mutate it and are safe to parallelise.
  fullyParallel: true,
  forbidOnly: isCI,
  // Locally a failure shows on the first run; retries would hide it.
  retries: isCI ? 2 : 0,
  // Every worker hammers ONE server, so keep the pool small.
  workers: env.E2E_WORKERS ?? 2,
  // The HTML report holds each failure's trace: `npm run test:e2e:report`.
  reporter: [
    [isCI ? "github" : "list"],
    ["html", { outputFolder: output.report, open: "never" }],
  ],
  // A test that genuinely needs longer uses `test.setTimeout`.
  timeout: TIMEOUTS.test,
  expect: { timeout: TIMEOUTS.expect },
  use: {
    baseURL: env.E2E_BASE_URL,
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
      testMatch: /.*\.setup\.ts/,
      // A cold dev server can reload the page mid-sign-in.
      retries: 2,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
    },
  ],
  // CI serves the static build: the dev server force-reloads the page when it
  // discovers a dependency to pre-bundle, wiping a test mid-way. Locally the
  // dev server picks up code changes, and one already running is reused.
  ...(env.startServer && {
    webServer: {
      command: isCI
        ? "npm run build:preview && npm run preview -- --port 3000 --strictPort --host 127.0.0.1"
        : "npm run dev",
      url: env.E2E_BASE_URL,
      reuseExistingServer: !isCI,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
    },
  }),
});
