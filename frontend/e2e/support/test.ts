import { test as base, expect } from "@playwright/test";

// Browser noise that isn't an app failure.
const BENIGN_PAGE_ERRORS = [/ResizeObserver loop/];

/** Options a project or `test.use()` can set. */
export interface E2EOptions {
  /** Opt-out for a test that causes app errors on purpose. */
  failOnAppErrors: boolean;
}

interface AutoFixtures {
  appErrorGuard: void;
}

/** `test` with a guard that fails any test the moment the app itself fails. */
export const test = base.extend<E2EOptions & AutoFixtures>({
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
      const fail = (message: string) => {
        errors.push(message);
        void page.close();
      };
      page.on("response", (response) => {
        const { pathname } = new URL(response.url());
        if (pathname.startsWith("/api/") && response.status() >= 500) {
          const method = response.request().method();
          fail(`${method} ${pathname} returned ${response.status()}`);
        }
      });
      page.on("pageerror", (error) => {
        if (BENIGN_PAGE_ERRORS.some((re) => re.test(error.message))) return;
        fail(`Uncaught error in the app: ${error.message}`);
      });

      await use();

      expect(errors, "The app failed while this test ran").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
