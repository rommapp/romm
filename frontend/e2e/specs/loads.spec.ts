import type { Page, Request } from "@playwright/test";
import { ROUTES, type RouteName } from "../../src/plugins/routeNames";
import { ROLES, STORAGE_STATE } from "../support/auth";
import {
  gotoFirstPlatform,
  gotoFirstRom,
  gotoHydrated,
  gotoOwnProfile,
} from "../support/navigation";
import { expect, test } from "../support/test";

// Every page opens for each role allowed on it with each document and API
// response 2xx, and a viewer gets the 404 page on admin-only ones.

/** Opened by URL, or by clicking through when the URL holds an id. */
type Opener = string | ((page: Page) => Promise<void>);

type PageDef =
  | { open: Opener }
  // A URL, so the viewer's 404 check can open it.
  | {
      open: string;
      /** The router sends a viewer without the route's scopes to the 404 page. */
      adminOnly: true;
    }
  | { skip: string };

// Keyed by every route the router knows, so a new route fails the typecheck
// until it is listed here or skipped with a reason.
const PAGES: Record<RouteName, PageDef> = {
  [ROUTES.HOME]: { open: "/" },
  [ROUTES.PLATFORMS_INDEX]: { open: "/platforms" },
  [ROUTES.PLATFORM]: { open: gotoFirstPlatform },
  [ROUTES.COLLECTIONS_INDEX]: { open: "/collections" },
  [ROUTES.SEARCH]: { open: "/search" },
  [ROUTES.MUSIC]: { open: "/music" },
  [ROUTES.ROM]: { open: gotoFirstRom },
  [ROUTES.SCAN]: { open: "/scan", adminOnly: true },
  [ROUTES.UPLOAD]: { open: "/upload", adminOnly: true },
  [ROUTES.ACTIVITY]: { open: "/activity" },
  [ROUTES.NOTIFICATIONS]: { open: "/notifications" },
  [ROUTES.USER_PROFILE]: { open: gotoOwnProfile },
  [ROUTES.USER_INTERFACE]: { open: "/user-interface" },
  [ROUTES.LIBRARY_MANAGEMENT]: {
    open: "/library-management",
    adminOnly: true,
  },
  [ROUTES.SCAN_SETTINGS]: { open: "/scan-settings", adminOnly: true },
  [ROUTES.CONVERSION_SETTINGS]: {
    open: "/conversion-settings",
    adminOnly: true,
  },
  [ROUTES.METADATA_SOURCES]: { open: "/metadata-sources" },
  [ROUTES.CLIENT_API_TOKENS]: { open: "/client-api-tokens" },
  [ROUTES.DEVICES]: { open: "/devices" },
  [ROUTES.ADMINISTRATION]: { open: "/administration", adminOnly: true },
  [ROUTES.SERVER_STATS]: { open: "/server-stats" },
  [ROUTES.LOGS]: { open: "/logs", adminOnly: true },
  [ROUTES.CONTROLLER_DEBUG]: { open: "/controller-debug" },

  [ROUTES.MAIN]: { skip: "the layout around the pages listed here" },
  [ROUTES.SETUP]: { skip: "only reachable before the first account exists" },
  [ROUTES.LOGIN]: { skip: "signed out; login.spec.ts covers it" },
  [ROUTES.RESET_PASSWORD]: { skip: "signed out, and needs a reset token" },
  [ROUTES.REGISTER]: { skip: "signed out, and needs an invite token" },
  [ROUTES.COLLECTION]: { skip: "needs a collection the library may lack" },
  [ROUTES.VIRTUAL_COLLECTION]: { skip: "needs a virtual collection" },
  [ROUTES.SMART_COLLECTION]: { skip: "needs a smart collection" },
  [ROUTES.EMULATORJS]: { skip: "a player: needs a game it can run" },
  [ROUTES.JSDOS]: { skip: "a player: needs a game it can run" },
  [ROUTES.PICO8]: { skip: "a player: needs a game it can run" },
  [ROUTES.EASYRPG]: { skip: "a player: needs a game it can run" },
  [ROUTES.RUFFLE]: { skip: "a player: needs a game it can run" },
  [ROUTES.STREAM]: { skip: "needs a streaming host" },
  [ROUTES.STREAM_DESKTOP]: { skip: "needs a streaming host" },
  [ROUTES.PAIR]: { skip: "needs a second device" },
  [ROUTES.PAIR_DEVICE]: { skip: "needs a second device" },
  [ROUTES.APRIL_FOOLS]: { skip: "an easter egg" },
  [ROUTES.CONSOLE_HOME]: { skip: "console mode, part of the frozen v1 UI" },
  [ROUTES.CONSOLE_PLATFORM]: { skip: "console mode, part of the v1 UI" },
  [ROUTES.CONSOLE_COLLECTION]: { skip: "console mode, part of the v1 UI" },
  [ROUTES.CONSOLE_SMART_COLLECTION]: { skip: "console mode, part of v1" },
  [ROUTES.CONSOLE_VIRTUAL_COLLECTION]: { skip: "console mode, part of v1" },
  [ROUTES.CONSOLE_ROM]: { skip: "console mode, part of the v1 UI" },
  [ROUTES.CONSOLE_PLAY]: { skip: "console mode, part of the v1 UI" },
  [ROUTES.NOT_FOUND]: { skip: "the viewer checks on admin-only pages" },
};

/** A request the page's load depends on: a document or an API call. */
function isLoadRequest(request: Request) {
  return (
    request.isNavigationRequest() ||
    new URL(request.url()).pathname.startsWith("/api/")
  );
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
  if ("skip" in def) continue;
  const adminOnly = "adminOnly" in def;

  test.describe(name, { tag: `@page:${name}` }, () => {
    for (const role of adminOnly ? (["admin"] as const) : ROLES) {
      test.describe(role, () => {
        test.use({ storageState: STORAGE_STATE[role] });

        test("loads", async ({ page }) => {
          await expectPageLoads(page, name, def.open);
        });
      });
    }

    if ("adminOnly" in def) {
      test.describe("viewer", () => {
        test.use({ storageState: STORAGE_STATE.viewer });

        test("gets the 404 page", async ({ page }) => {
          await gotoHydrated(page, def.open);
          await expect(page.locator(".r-v2-notfound")).toBeVisible();
        });
      });
    }
  });
}
