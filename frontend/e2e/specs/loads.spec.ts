import type { Locator, Page, Request } from "@playwright/test";
import type { RouteName } from "../../src/plugins/routeNames";
import { ROLES, STORAGE_STATE } from "../support/auth";
import { gotoHydrated } from "../support/navigation";
import {
  isAdminOnly,
  type Opener,
  openPage,
  PAGES,
  type PageDef,
} from "../support/pages";
import { expect, test } from "../support/test";

// Every page opens for each role allowed on it with each document and API
// response 2xx, and a viewer gets the 404 page on admin-only ones.

/** A request the page's load depends on: a document or an API call. */
function isLoadRequest(request: Request) {
  return (
    request.isNavigationRequest() ||
    new URL(request.url()).pathname.startsWith("/api/")
  );
}

function notFoundHeading(page: Page): Locator {
  return page.getByRole("heading", { name: "Page not found" });
}

async function expectPageLoads(page: Page, name: string, open: Opener) {
  const failed: string[] = [];
  page.on("response", (response) => {
    if (isLoadRequest(response.request()) && !response.ok()) {
      const { pathname } = new URL(response.url());
      failed.push(
        `${response.request().method()} ${pathname} returned ${response.status()}`,
      );
    }
  });

  await openPage(page, open);
  await expect(notFoundHeading(page)).toHaveCount(0);
  expect(
    failed,
    `Responses that failed while loading ${name} (a 404 from /api usually means the site's backend is older than this branch)`,
  ).toEqual([]);
}

for (const [name, def] of Object.entries(PAGES) as [RouteName, PageDef][]) {
  if ("skip" in def) continue;
  const { open } = def;
  const adminOnly = isAdminOnly(name);
  if (adminOnly && typeof open !== "string") {
    throw new Error(`${name} is admin-only, so it needs a URL for the viewer.`);
  }

  test.describe(name, { tag: `@page:${name}` }, () => {
    for (const role of adminOnly ? (["admin"] as const) : ROLES) {
      test.describe(role, () => {
        test.use({ storageState: STORAGE_STATE[role] });

        test("loads", async ({ page }) => {
          await expectPageLoads(page, name, open);
        });
      });
    }

    if (adminOnly && typeof open === "string") {
      test.describe("viewer", () => {
        test.use({ storageState: STORAGE_STATE.viewer });

        test("gets the 404 page", async ({ page }) => {
          await gotoHydrated(page, open);
          await expect(notFoundHeading(page)).toBeVisible();
        });
      });
    }
  });
}
