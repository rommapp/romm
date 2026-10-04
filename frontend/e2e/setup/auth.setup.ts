import {
  ACCOUNTS,
  fillLoginForm,
  ROLES,
  seedUiState,
  STORAGE_STATE,
} from "../support/auth";
import { expect, test as setup } from "../support/test";

// Signs each account in and saves its session, so specs start authenticated
// with `test.use({ storageState })`. login.spec.ts tests the form itself.
for (const role of ROLES) {
  setup(`authenticate as ${role}`, async ({ page }) => {
    // The first load can compile the app on a cold dev server.
    setup.slow();
    const { username, password } = ACCOUNTS[role];

    await seedUiState(page);
    await page.goto("/login");
    const answered = page.waitForResponse(
      (r) => r.url().endsWith("/api/login") && r.request().method() === "POST",
    );
    await fillLoginForm(page, username, password);
    const response = await answered;
    expect(response.status(), `POST /api/login for ${username}`).toBe(200);
    // The app bar's user name only renders once the session is established.
    await expect(page.locator(".r-v2-user__name")).toHaveText(username);

    await page.context().storageState({ path: STORAGE_STATE[role] });
  });
}
