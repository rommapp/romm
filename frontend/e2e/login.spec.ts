import { accountFor, fillLoginForm, seedUiState } from "./fixtures/auth";
import { expect, test } from "./fixtures/test";

// The only spec that drives the login form. Every other spec starts from a
// session saved by auth.setup.ts, so this is the single place the form, the
// session cookie and the post-login redirect are actually exercised.
//
// It starts explicitly signed out, whatever sessions are saved in e2e/.auth/ or
// set elsewhere in the config: exercising the form is the whole point.
test.use({ storageState: { cookies: [], origins: [] } });

test.describe("Login", () => {
  test("signs in and lands on the app", async ({ page, e2eEnv }) => {
    const { username, password } = accountFor(e2eEnv, "viewer");
    await seedUiState(page, "dark");
    await page.goto("/login");

    await fillLoginForm(page, username, password);

    // The app bar's user name only renders once the session is established and
    // the auth store holds a user -- a stronger signal than "the URL changed".
    await expect(page.locator(".r-v2-user__name")).toHaveText(username);
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("rejects a wrong password and stays put", async ({ page, e2eEnv }) => {
    const { username } = accountFor(e2eEnv, "viewer");
    await seedUiState(page, "dark");
    await page.goto("/login");

    await fillLoginForm(page, username, "definitely-not-it");

    // Stays on /login with no session. Asserted via the app bar's absence
    // rather than a snackbar, so the test doesn't depend on toast copy.
    await expect(page.locator(".r-v2-user__name")).toHaveCount(0);
    await expect(page).toHaveURL(/\/login/);
  });

  // Tagged @devices: a cheap smoke test that the app boots on every device.
  test(
    "an unauthenticated visitor is redirected to login",
    { tag: "@devices" },
    async ({ page }) => {
      await seedUiState(page, "dark");
      await page.goto("/");

      await expect(page).toHaveURL(/\/login/);
      await expect(page.locator("form.r-v2-login-form")).toBeVisible();
    },
  );
});
