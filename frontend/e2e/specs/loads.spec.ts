import type { Page, Response } from "@playwright/test";
import {
  gotoFirstRom,
  gotoHydrated,
  gotoOwnProfile,
  seedUiState,
  STORAGE_STATE,
} from "../support/auth";
import { expect, test } from "../support/test";

// Every signed-in page opens with each document and API response 2xx. Each is
// tagged `@page:<name>`, like the page's other specs: `--grep "@page:home\b"`.
//
// Not listed, because they need specific game files, a second device, or data a
// library may not have: the players (/rom/:id/ejs, jsdos, pico8, ruffle,
// stream), /stream/desktop, /pair, and single collections.

type PageDef = {
  /** Opened by URL, or by clicking through when the URL holds an id. */
  open: string | ((page: Page) => Promise<void>);
  /** The router sends a viewer without the route's scopes to the 404 page. */
  adminOnly?: boolean;
};

const PAGES: Record<string, PageDef> = {
  home: { open: "/" },
  platforms: { open: "/platforms" },
  platform: {
    open: async (page) => {
      await gotoHydrated(page, "/platforms");
      await page.locator('a[href^="/platform/"]').first().click();
      await expect(page).toHaveURL(/\/platform\/\d+/);
    },
  },
  collections: { open: "/collections" },
  search: { open: "/search" },
  music: { open: "/music" },
  gameDetails: { open: gotoFirstRom },
  scan: { open: "/scan", adminOnly: true },
  upload: { open: "/upload", adminOnly: true },
  activity: { open: "/activity" },
  notifications: { open: "/notifications" },
  profile: { open: gotoOwnProfile },
  userInterface: { open: "/user-interface" },
  libraryManagement: { open: "/library-management", adminOnly: true },
  scanSettings: { open: "/scan-settings", adminOnly: true },
  metadataSources: { open: "/metadata-sources" },
  clientApiTokens: { open: "/client-api-tokens" },
  administration: { open: "/administration", adminOnly: true },
  serverStats: { open: "/server-stats" },
  logs: { open: "/logs", adminOnly: true },
  controllerDebug: { open: "/controller-debug" },
};

/** A response the page's load depends on: a document or an API call. */
function isLoadResponse(response: Response) {
  return (
    response.request().isNavigationRequest() ||
    new URL(response.url()).pathname.startsWith("/api/")
  );
}

async function expectPageLoads(page: Page, name: string, { open }: PageDef) {
  const failed: string[] = [];
  page.on("response", (response) => {
    if (isLoadResponse(response) && !response.ok()) {
      const { pathname } = new URL(response.url());
      failed.push(
        `${response.request().method()} ${pathname} returned ${response.status()}`,
      );
    }
  });

  if (typeof open === "string") {
    await gotoHydrated(page, open);
    // A route guard that bounced us elsewhere (home, login) fails here.
    await expect(page).toHaveURL(
      (url) => url.pathname === open || url.pathname.startsWith(`${open}/`),
    );
  } else {
    await open(page);
  }

  // The router-view's content, which exists only once the lazy view resolves.
  await expect(page.locator("#r-v2-main > *").first()).toBeVisible();
  await expect(page.locator(".r-v2-notfound")).toHaveCount(0);
  expect(
    failed,
    `Responses that failed while loading ${name} (a 404 from /api usually means the site's backend is older than this branch)`,
  ).toEqual([]);
}

for (const [name, def] of Object.entries(PAGES)) {
  test.describe(name, { tag: `@page:${name}` }, () => {
    test.describe("admin", () => {
      test.use({ storageState: STORAGE_STATE.admin });

      test("loads", async ({ page }) => {
        await seedUiState(page, "dark");
        await expectPageLoads(page, name, def);
      });
    });

    if (def.adminOnly && typeof def.open === "string") {
      const path = def.open;

      test.describe("viewer", () => {
        test.use({ storageState: STORAGE_STATE.viewer });

        test("gets the 404 page", async ({ page }) => {
          await seedUiState(page, "dark");
          await gotoHydrated(page, path);
          await expect(page.locator(".r-v2-notfound")).toBeVisible();
        });
      });
    }
  });
}
