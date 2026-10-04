import type { Page } from "@playwright/test";
import type { E2EEnv } from "./e2e-environment";
import { AUTH_DIR } from "./output";
import { expect } from "./test";

export type Role = "admin" | "viewer";

export const ROLES = ["admin", "viewer"] as const satisfies readonly Role[];

export interface Account {
  username: string;
  password: string;
}

/** The account every permission assertion for `role` is made against. */
export function accountFor(env: E2EEnv, role: Role): Account {
  return role === "admin"
    ? { username: env.E2E_ADMIN_USERNAME, password: env.E2E_ADMIN_PASSWORD }
    : { username: env.E2E_VIEWER_USERNAME, password: env.E2E_VIEWER_PASSWORD };
}

/** Where auth.setup.ts saves each role's session (gitignored: live cookies). */
export const STORAGE_STATE: Record<Role, string> = {
  admin: `${AUTH_DIR}/admin.json`,
  viewer: `${AUTH_DIR}/viewer.json`,
};

/** Fill and submit the login form.
 *
 *  Scoped to `form.r-v2-login-form`: the collapsed reset-password form has its
 *  own submit button and fields, so unscoped selectors hit strict mode. */
export async function fillLoginForm(
  page: Page,
  username: string,
  password: string,
) {
  const form = page.locator("form.r-v2-login-form");
  await form.locator('input[name="username"]').fill(username);
  await form.locator('input[name="password"]').fill(password);
  await form.locator('button[type="submit"]').click();
}

/** Open the account menu and follow its Profile link (route `/user/:user`). */
export async function gotoOwnProfile(page: Page) {
  await gotoHydrated(page, "/");
  await page.locator("[data-user-menu-trigger]").click();
  await page.getByRole("menuitem", { name: "Profile" }).click();
  await expect(page).toHaveURL(/\/user\/\d+/);
}

/** Open the first platform on the platforms index, then its first game. */
export async function gotoFirstRom(page: Page) {
  await gotoHydrated(page, "/platforms");
  await page.locator('a[href^="/platform/"]').first().click();
  await page.locator('a.r-gc[href^="/rom/"]').first().click();
  await expect(page).toHaveURL(/\/rom\/\d+/);
}

/** `page.goto` that also waits for the permissions store to hydrate.
 *
 *  `useCan` reads grants from `/permissions/me` after mount, so until then even
 *  an admin sees every gated control hidden. The listener is armed before
 *  navigating, and any status is checked so a 401/403 fails with its cause.
 *  A rejected session redirects to /login, which never requests permissions,
 *  so the login form is raced against the response. */
export async function gotoHydrated(page: Page, path: string) {
  const hydrated = page.waitForResponse((r) =>
    r.url().includes("/api/permissions/me"),
  );
  await page.goto(path);
  const loginShown = page.locator("form.r-v2-login-form").waitFor();
  const response = await Promise.race([hydrated, loginShown.then(() => null)]);
  if (!response) {
    throw new Error(
      `Opened ${path} but landed on the login page: the backend rejected this test's saved session.`,
    );
  }
  if (!response.ok()) {
    throw new Error(
      `Permissions didn't load (GET /api/permissions/me returned ${response.status()}). The backend most likely rejected this test's saved session.`,
    );
  }
  // Renders once the auth store holds a user: the app shell is ready.
  await expect(page.locator(".r-v2-user__name")).toBeVisible();
}

/** Open the ⋯ more-actions menu and return the teleported panel locator. */
export async function openMoreMenu(page: Page) {
  await page.getByRole("button", { name: "More actions" }).first().click();
  const panel = page.locator('[role="menu"]');
  await expect(panel).toBeVisible();
  return panel;
}

/** Visible labels of every item in an open menu panel, in DOM order. */
export async function menuLabels(page: Page): Promise<string[]> {
  return page.locator('[role="menu"] .r-menu-item__label').allInnerTexts();
}

/** Force the v2 UI and a known theme before the app boots. */
export async function seedUiState(page: Page, theme: "dark" | "light") {
  await page.addInitScript((t) => {
    // Init scripts also run in Chrome's own error page, which denies storage.
    if (!location.protocol.startsWith("http")) return;
    const seeded = { "settings.uiVersion": "v2", "settings.theme": t };
    // The app only adopts an unscoped value when the signed-in user has no
    // `user:<id>:` copy, and a saved session carries one.
    for (const key of Object.keys(localStorage)) {
      const scoped = /^user:\d+:(.+)$/.exec(key)?.[1];
      if (scoped && scoped in seeded) localStorage.removeItem(key);
    }
    for (const [key, value] of Object.entries(seeded)) {
      localStorage.setItem(key, value);
    }
  }, theme);
}
