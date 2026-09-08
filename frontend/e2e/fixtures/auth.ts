import { expect, type Page } from "@playwright/test";

// Fixture accounts seeded by `.github/scripts/seed_e2e_users.py`.
export const USERS = {
  admin: process.env.E2E_ADMIN_USERNAME ?? "e2e_admin",
  viewer: process.env.E2E_VIEWER_USERNAME ?? "e2e_viewer",
} as const;

export const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-Passw0rd!";

export type Role = keyof typeof USERS;

/** Where auth.setup.ts parks each role's authenticated session. Gitignored --
 *  they hold live session cookies and are regenerated on every run. */
export const STORAGE_STATE: Record<Role, string> = {
  admin: "playwright/.auth/admin.json",
  viewer: "playwright/.auth/viewer.json",
};

/** Log in through the real form and wait for the app shell to take over.
 *
 *  Everything is scoped to `form.r-v2-login-form`. The reset-password form is
 *  rendered alongside it (collapsed, not unmounted) and has its own submit
 *  button and fields, so unscoped `button[type="submit"]` / `input[name=...]`
 *  selectors match two elements and blow up on strict mode. */
export async function login(
  page: Page,
  role: Role,
  {
    timeout = 25_000,
    attempts = 3,
  }: { timeout?: number; attempts?: number } = {},
) {
  // Retried because the Vite dev server force-reloads the page when it
  // discovers a new dependency to pre-bundle ("optimized dependencies changed.
  // reloading").
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      await page.goto("/login");
      const form = page.locator("form.r-v2-login-form");
      await form.locator('input[name="username"]').fill(USERS[role]);
      await form.locator('input[name="password"]').fill(PASSWORD);
      await form.locator('button[type="submit"]').click();
      // Assert a marker that only exists once authenticated (the app bar's user
      // name) rather than just "the URL is no longer /login" -- the latter goes
      // true mid-transition and says nothing about the session.
      await expect(page.locator(".r-v2-user__name")).toHaveText(USERS[role], {
        timeout,
      });
      await expect(page).not.toHaveURL(/\/login/);
      return;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

/** Navigate to the logged-in user's own profile page (route `/user/:user`). */
export async function gotoOwnProfile(page: Page) {
  const res = await page.request.get("/api/users/me");
  expect(res.ok(), "could not resolve the current user").toBe(true);
  const me = await res.json();
  await gotoHydrated(page, `/user/${me.id}`);
  return me;
}

/** Navigate to the first ROM of the first non-empty platform.
 *
 *  Waits for the permission grants to land before returning. `useCan` reads a
 *  store hydrated from `/permissions/me` AFTER the app mounts, so until that
 *  response arrives even an admin has no grants and every gated control is
 *  hidden. Asserting before then reads the pre-hydration menu -- which looks
 *  exactly like a permissions bug and is not one. */
export async function gotoFirstRom(page: Page) {
  const res = await page.request.get("/api/roms?limit=1&order_by=name");
  expect(res.ok(), "could not list ROMs -- is the dev library populated?").toBe(
    true,
  );
  const body = await res.json();
  const rom = body.items?.[0];
  expect(rom, "the dev library has no ROMs to test against").toBeTruthy();
  await gotoHydrated(page, `/rom/${rom.id}`);
  return rom;
}

/** `page.goto` that also waits for the permissions store to hydrate. The
 *  listener is armed BEFORE navigating, or the response can land first and the
 *  wait hangs until it times out. */
export async function gotoHydrated(page: Page, path: string) {
  const hydrated = page
    .waitForResponse(
      (r) => r.url().includes("/api/permissions/me") && r.status() === 200,
      // Short: hydration normally lands well under a second. A long timeout
      // here is actively harmful -- when the request doesn't fire, the catch
      // below still waits it out first, eating the test's own budget.
      { timeout: 10_000 },
    )
    // A cached/absent refetch shouldn't fail the navigation; the assertions
    // that follow are auto-waiting anyway.
    .catch(() => null);
  await page.goto(path);
  await hydrated;
  // The app bar's user name renders only once the auth store holds a user, so
  // it doubles as an "app shell is ready" signal. Without it, assertions can
  // run against a view still showing its loading skeleton -- which fails as a
  // missing element and reads like the element was removed on purpose.
  await expect(page.locator(".r-v2-user__name")).toBeVisible({
    timeout: 30_000,
  });
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
  await page.addInitScript(
    ([t]) => {
      localStorage.setItem("settings.uiVersion", "v2");
      localStorage.setItem("settings.theme", t);
    },
    [theme],
  );
}
