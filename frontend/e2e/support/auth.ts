import type { Browser, Page } from "@playwright/test";
import type { E2EEnv } from "./e2e-environment";
import { AUTH_DIR } from "./output";
import { expect, watchAppErrors } from "./test";

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

/** A login failure that retrying can't fix, so `login()` stops at once. */
class LoginRejected extends Error {}

/** Whether a saved session still signs `username` in, judged by what the app
 *  renders: that user's name in the app bar, or the login form. */
export async function isSessionValid(
  browser: Browser,
  {
    path,
    username,
    baseURL,
    timeout,
  }: { path: string; username: string; baseURL?: string; timeout: number },
): Promise<boolean> {
  const context = await browser
    .newContext({ baseURL, storageState: path, serviceWorkers: "block" })
    // An unreadable file is as good as no session.
    .catch(() => null);
  if (!context) return false;
  try {
    const page = await context.newPage();
    // A separate context, so the test's app-error guard doesn't see this page.
    const errors: string[] = [];
    watchAppErrors(page, (message) => {
      errors.push(message);
      void page.close();
    });
    const userName = page.locator(".r-v2-user__name");
    try {
      await page.goto("/");
      await userName
        .or(page.locator("form.r-v2-login-form"))
        .first()
        .waitFor({ timeout });
    } catch (error) {
      if (!errors.length) throw error;
    }
    if (errors.length) {
      throw new Error(
        `The app failed while checking the saved session for ${username}: ${errors.join("; ")}`,
      );
    }
    return (
      (await userName.isVisible()) &&
      (await userName.innerText()).trim() === username
    );
  } finally {
    await context.close();
  }
}

/** Log in through the real form and wait for the app shell to take over. */
export async function login(
  page: Page,
  { username, password }: Account,
  { timeout, attempts }: { timeout: number; attempts: number },
) {
  // Retried because the Vite dev server force-reloads the page when it
  // discovers a new dependency to pre-bundle.
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      await page.goto("/login");
      const answered = page.waitForResponse(
        (r) =>
          r.url().includes("/api/login") && r.request().method() === "POST",
      );
      await fillLoginForm(page, username, password);
      // A dead backend or bad credentials won't be fixed by waiting.
      const response = await answered;
      if (response.status() >= 500) {
        throw new LoginRejected(
          `The backend isn't answering (POST /api/login returned ${response.status()}). Is the site at E2E_BASE_URL up?`,
        );
      }
      if (!response.ok()) {
        throw new LoginRejected(
          `The backend rejected the ${username} account (POST /api/login returned ${response.status()}). Check its credentials in e2e/.env, and that it exists on that backend.`,
        );
      }
      // The app bar's user name only exists once authenticated; "the URL is no
      // longer /login" goes true mid-transition.
      await expect(page.locator(".r-v2-user__name")).toHaveText(username, {
        timeout,
      });
      await expect(page).not.toHaveURL(/\/login/);
      return;
    } catch (error) {
      if (error instanceof LoginRejected) throw error;
      lastError = error;
    }
  }
  throw lastError;
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
 *  An expired session redirects to /login, which never requests permissions,
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
      `Opened ${path} but landed on the login page: the saved session for this test has expired or was rejected. Run again, and setup signs in afresh (or delete e2e/.output/auth/).`,
    );
  }
  if (!response.ok()) {
    throw new Error(
      `Permissions didn't load (GET /api/permissions/me returned ${response.status()}). The session most likely expired: run again, or delete e2e/.output/auth/ to force a fresh sign-in.`,
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
    localStorage.setItem("settings.uiVersion", "v2");
    localStorage.setItem("settings.theme", t);
  }, theme);
}
