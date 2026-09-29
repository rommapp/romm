import { test as base, expect, type Page } from "@playwright/test";
import { type E2EEnv, readE2EEnv } from "./e2e-environment";

// Browser noise that isn't an app failure.
const BENIGN_PAGE_ERRORS = [/ResizeObserver loop/];

/** Call `onError` with a message naming each /api 5xx or uncaught error. */
export function watchAppErrors(page: Page, onError: (message: string) => void) {
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (url.pathname.startsWith("/api/") && response.status() >= 500) {
      const method = response.request().method();
      onError(`${method} ${url.pathname} returned ${response.status()}`);
    }
  });
  page.on("pageerror", (error) => {
    if (BENIGN_PAGE_ERRORS.some((re) => re.test(error.message))) return;
    onError(`Uncaught error in the app: ${error.message}`);
  });
}

/** Options a project or `test.use()` can set. */
export interface E2EOptions {
  /** Opt-out for a test that causes app errors on purpose. */
  failOnAppErrors: boolean;
}

interface AutoFixtures {
  appErrorGuard: void;
}

/** `test` with the validated environment as `e2eEnv`, and a guard that fails
 *  any test the moment the app itself fails. */
export const test = base.extend<E2EOptions & AutoFixtures, { e2eEnv: E2EEnv }>({
  failOnAppErrors: [true, { option: true }],

  // An /api 5xx or an uncaught exception otherwise surfaces as a locator
  // timeout later, blaming an element. Closing the page fails the wait at once.
  appErrorGuard: [
    async ({ page, failOnAppErrors }, use) => {
      if (!failOnAppErrors) {
        await use();
        return;
      }
      const errors: string[] = [];
      watchAppErrors(page, (message) => {
        errors.push(message);
        void page.close();
      });

      await use();

      expect(errors, "The app failed while this test ran").toEqual([]);
    },
    { auto: true },
  ],

  e2eEnv: [
    // Playwright requires a destructured first argument, even when empty.
    async ({}, use) => {
      await use(readE2EEnv());
    },
    { scope: "worker" },
  ],
});

export { expect };
