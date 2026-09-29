import type { Page, Request } from "@playwright/test";
import {
  gotoFirstRom,
  gotoHydrated,
  gotoOwnProfile,
  seedUiState,
  SIGNED_OUT,
  STORAGE_STATE,
} from "../support/auth";
import {
  E2E_SITEMAP,
  SMOKE,
  type E2eSitemapEntry,
  type E2eSitemapId,
} from "../support/sitemap";
import { expect, test } from "../support/test";

// Every signed-in page opens with each document and API response 2xx. Each is
// tagged `@page:<name>`, like the page's other specs: `--grep "@page:home\b"`.
//
// Not listed, because they need specific game files, a second device, or data a
// library may not have: the players (/rom/:id/ejs, jsdos, pico8, ruffle,
// stream), /stream/desktop, /pair, and single collections.

export type PageDef = {
  /** Opened by URL, or by clicking through when the URL holds an id. */
  open: string | ((page: Page) => Promise<void>);
  /** The router sends a viewer without the route's scopes to the 404 page. */
  adminOnly?: boolean;
} & Pick<E2eSitemapEntry, "tag">;

// Pages whose URL holds an id, so they're reached by clicking through.
const CLICK_THROUGH_PAGES: Record<string, PageDef> = {
  platform: {
    open: async (page) => {
      await gotoHydrated(page, "/platforms");
      await page.locator('a[href^="/platform/"]').first().click();
      await expect(page).toHaveURL(/\/platform\/\d+/);
    },
    tag: ["@page:platform"],
  },
  gameDetails: { open: gotoFirstRom, tag: ["@page:gameDetails"] },
  profile: { open: gotoOwnProfile, tag: ["@page:profile"] },
};

// Pages whose load check is part of the merge gate.
const SMOKE_PAGES: readonly E2eSitemapId[] = [
  "home",
  "platforms",
  "search",
  "administration",
];

export const PAGES: Record<string, PageDef> = {
  ...Object.fromEntries(
    E2E_SITEMAP.filter(({ storageState }) => storageState !== SIGNED_OUT).map(
      ({ id, path, storageState, tag }) => [
        id,
        {
          open: path,
          adminOnly: storageState === STORAGE_STATE.admin,
          tag: SMOKE_PAGES.includes(id) ? [SMOKE, ...tag] : tag,
        },
      ],
    ),
  ),
  ...CLICK_THROUGH_PAGES,
};

/** A request the page's load depends on: a document or an API call. */
function isLoadRequest(request: Request) {
  return (
    request.isNavigationRequest() ||
    new URL(request.url()).pathname.startsWith("/api/")
  );
}

async function expectPageLoads(page: Page, name: string, { open }: PageDef) {
  const pending = new Set<Request>();
  const settle = (request: Request) => pending.delete(request);
  page.on("request", (request) => {
    if (isLoadRequest(request)) pending.add(request);
  });
  page.on("requestfinished", settle);
  page.on("requestfailed", settle);

  const failed: string[] = [];
  page.on("response", (response) => {
    if (isLoadRequest(response.request()) && !response.ok()) {
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
  // Mount-time API calls can outlive the first render; their failures count too.
  await expect
    .poll(() => pending.size, {
      message: `${name} still has requests in flight`,
    })
    .toBe(0);
  expect(
    failed,
    `Responses that failed while loading ${name} (a 404 from /api usually means the site's backend is older than this branch)`,
  ).toEqual([]);
}

for (const [name, def] of Object.entries(PAGES)) {
  test.describe(name, { tag: [...def.tag] }, () => {
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
