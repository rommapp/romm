import {
  ACCOUNTS,
  fillLoginForm,
  loginForm,
  seedUiState,
  signedInUser,
} from "../../support/auth";
import { expect, test } from "../../support/test";

// The only spec that drives the login form. Every other spec starts from a
// session saved by auth.setup.ts, so this is the single place the form, the
// session cookie and the post-login redirect are actually exercised.
//
// It starts explicitly signed out, whatever sessions are saved in e2e/.output/auth/ or
// set elsewhere in the config: exercising the form is the whole point.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Login", () => {
  test.beforeEach(async ({ page }) => {
    await seedUiState(page);
  });

  test("signs in and lands on the app", async ({ page }) => {
    const { username, password } = ACCOUNTS.viewer;
    await page.goto("/login");

    await fillLoginForm(page, username, password);

    // The app bar's user name only renders once the session is established and
    // the auth store holds a user -- a stronger signal than "the URL changed".
    await expect(signedInUser(page)).toHaveText(username, {
      ignoreCase: true,
    });
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("rejects a wrong password and stays put", async ({ page }) => {
    const { username } = ACCOUNTS.viewer;
    await page.goto("/login");

    await fillLoginForm(page, username, "definitely-not-it");

    // Stays on /login with no session. Asserted via the app bar's absence
    // rather than a snackbar, so the test doesn't depend on toast copy.
    await expect(signedInUser(page)).toHaveCount(0);
    await expect(page).toHaveURL(/\/login/);
  });

  test("an unauthenticated visitor is redirected to login", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page).toHaveURL(/\/login/);
    await expect(loginForm(page)).toBeVisible();
  });
});
