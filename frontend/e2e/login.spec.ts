import { expect, test } from "@playwright/test";
import { PASSWORD, seedUiState, USERS } from "./fixtures/auth";

// The only spec that drives the login form. Every other spec starts from a
// session saved by auth.setup.ts, so this is the single place the form, the
// session cookie and the post-login redirect are actually exercised.
//
// It uses the default (unauthenticated) `page` fixture -- no
// `test.use({ storageState })` here, which is the whole point.
test.describe("Login", () => {
  test("signs in and lands on the app", async ({ page }) => {
    await seedUiState(page, "dark");
    await page.goto("/login");

    const form = page.locator("form.r-v2-login-form");
    await form.locator('input[name="username"]').fill(USERS.viewer);
    await form.locator('input[name="password"]').fill(PASSWORD);
    await form.locator('button[type="submit"]').click();

    // The app bar's user name only renders once the session is established and
    // the auth store holds a user -- a stronger signal than "the URL changed".
    await expect(page.locator(".r-v2-user__name")).toHaveText(USERS.viewer);
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("rejects a wrong password and stays put", async ({ page }) => {
    await seedUiState(page, "dark");
    await page.goto("/login");

    const form = page.locator("form.r-v2-login-form");
    await form.locator('input[name="username"]').fill(USERS.viewer);
    await form.locator('input[name="password"]').fill("definitely-not-it");
    await form.locator('button[type="submit"]').click();

    // Stays on /login with no session. Asserted via the app bar's absence
    // rather than a snackbar, so the test doesn't depend on toast copy.
    await expect(page.locator(".r-v2-user__name")).toHaveCount(0);
    await expect(page).toHaveURL(/\/login/);
  });

  test("an unauthenticated visitor is redirected to login", async ({
    page,
  }) => {
    await seedUiState(page, "dark");
    await page.goto("/");

    await expect(page).toHaveURL(/\/login/);
    await expect(page.locator("form.r-v2-login-form")).toBeVisible();
  });
});
