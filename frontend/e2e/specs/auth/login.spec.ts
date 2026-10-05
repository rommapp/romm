import {
  ACCOUNTS,
  accountMenu,
  fillLoginForm,
  loginButton,
  seedUiState,
} from "../../support/auth";
import { expect, test } from "../../support/test";

// The only spec that drives the login form; the others reuse auth.setup.ts's
// sessions. It starts signed out, whatever sessions are saved.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Login", () => {
  test.beforeEach(async ({ page }) => {
    await seedUiState(page);
  });

  test("signs in and lands on the app", async ({ page }) => {
    const { username, password } = ACCOUNTS.viewer;
    await page.goto("/login");

    await fillLoginForm(page, username, password);

    // The account menu takes the user's name once the auth store holds one,
    // which a URL change alone doesn't prove.
    await expect(accountMenu(page, username)).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("rejects a wrong password and stays put", async ({ page }) => {
    const { username } = ACCOUNTS.viewer;
    await page.goto("/login");

    await fillLoginForm(page, username, "definitely-not-it");

    // Stays on /login with no session. Asserted via the app bar's absence
    // rather than a snackbar, so the test doesn't depend on toast copy.
    await expect(accountMenu(page)).toHaveCount(0);
    await expect(page).toHaveURL(/\/login/);
  });

  test("an unauthenticated visitor is redirected to login", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page).toHaveURL(/\/login/);
    await expect(loginButton(page)).toBeVisible();
  });
});
