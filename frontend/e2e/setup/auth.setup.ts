import {
  accountFor,
  fillLoginForm,
  ROLES,
  seedUiState,
  STORAGE_STATE,
} from "../support/auth";
import { expect, test as setup } from "../support/test";

// Signs each account in and saves its session, so specs start authenticated
// with `test.use({ storageState })`. login.spec.ts tests the form itself.
for (const role of ROLES) {
  setup(`authenticate as ${role}`, async ({ page, e2eEnv }) => {
    // The first load can compile the app on a cold dev server.
    setup.slow();
    const { username, password } = accountFor(e2eEnv, role);

    await seedUiState(page, "dark");
    await page.goto("/login");
    await fillLoginForm(page, username, password);
    // The app bar's user name only renders once the session is established.
    await expect(page.locator(".r-v2-user__name")).toHaveText(username);

    await page.context().storageState({ path: STORAGE_STATE[role] });
  });
}
