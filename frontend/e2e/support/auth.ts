import type { Locator, Page } from "@playwright/test";
import { AUTH_DIR } from "./output";

const { env } = process;

// The seed script sets both accounts' password from E2E_PASSWORD.
const SEEDED_PASSWORD = env.E2E_PASSWORD || "e2e-Passw0rd!";

// The accounts every permission assertion is made against. The defaults are
// the ones .github/scripts/seed_e2e_users.py creates.
export const ACCOUNTS = {
  admin: {
    username: env.E2E_ADMIN_USERNAME || "e2e_admin",
    password: env.E2E_ADMIN_PASSWORD || SEEDED_PASSWORD,
  },
  viewer: {
    username: env.E2E_VIEWER_USERNAME || "e2e_viewer",
    password: env.E2E_VIEWER_PASSWORD || SEEDED_PASSWORD,
  },
};

export type Role = keyof typeof ACCOUNTS;

export const ROLES = Object.keys(ACCOUNTS) as Role[];

/** Where auth.setup.ts saves each role's session (gitignored: live cookies). */
export const STORAGE_STATE = Object.fromEntries(
  ROLES.map((role) => [role, `${AUTH_DIR}/${role}.json`]),
) as Record<Role, string>;

/** The v2 login form, not the collapsed reset-password form beside it. */
export function loginForm(page: Page): Locator {
  return page.locator("form.r-v2-login-form");
}

/** The app bar's user name, rendered once the session is established. */
export function signedInUser(page: Page): Locator {
  return page.locator(".r-v2-user__name");
}

/** Fill and submit the login form. */
export async function fillLoginForm(
  page: Page,
  username: string,
  password: string,
) {
  const form = loginForm(page);
  await form.locator('input[name="username"]').fill(username);
  await form.locator('input[name="password"]').fill(password);
  await form.locator('button[type="submit"]').click();
}

/** Force the v2 UI before the app boots, with the theme following the
 *  browser's `colorScheme`. The app syncs these settings to the user's
 *  account, so "auto" is the only theme the suite ever stores there. */
export async function seedUiState(page: Page) {
  await page.addInitScript(() => {
    // Init scripts also run in Chrome's own error page, which denies storage.
    if (!location.protocol.startsWith("http")) return;
    const seeded = { "settings.uiVersion": "v2", "settings.theme": "auto" };
    // The app only adopts an unscoped value when the signed-in user has no
    // `user:<id>:` copy, and a saved session carries one.
    for (const key of Object.keys(localStorage)) {
      const scoped = /^user:\d+:(.+)$/.exec(key)?.[1];
      if (scoped && Object.hasOwn(seeded, scoped)) localStorage.removeItem(key);
    }
    for (const [key, value] of Object.entries(seeded)) {
      localStorage.setItem(key, value);
    }
  });
}
