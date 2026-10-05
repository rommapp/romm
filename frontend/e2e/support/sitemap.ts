import type { BrowserContextOptions, Page } from "@playwright/test";
import {
  ROUTE_SCOPES,
  ROUTES,
  type RouteName,
} from "../../src/plugins/routeNames";
import { SIGNED_OUT, STORAGE_STATE } from "./auth";
import {
  clickThroughToFirstRom,
  gotoFirstPlatform,
  gotoOwnProfile,
} from "./navigation";

// Every tag the suite uses, defined once.
export type E2eTag = typeof SMOKE | `@page:${RouteName}`;

// Gates a merge. Spread it into the specific tests that belong in the gate,
// never onto a sitemap entry, or axe and lighthouse inherit it.
export const SMOKE = "@smoke";

export function pageTag(name: RouteName): E2eTag {
  return `@page:${name}`;
}

/** Opened by URL, or by clicking through when the URL holds an id. */
export type Opener = string | ((page: Page) => Promise<void>);

export type PageDef = { open: Opener } | { skip: string };

// Scope-gated routes the seeded Viewer group still opens. Every other route in
// ROUTE_SCOPES is admin-only, so a newly gated route gets the viewer 404 check.
const VIEWER_OPENS: ReadonlySet<RouteName> = new Set([
  ROUTES.CLIENT_API_TOKENS,
  ROUTES.DEVICES,
]);

export function isAdminOnly(name: RouteName): boolean {
  return name in ROUTE_SCOPES && !VIEWER_OPENS.has(name);
}

// Keyed by every route the router knows, so a new route fails the typecheck
// until it is listed here or skipped with a reason.
export const PAGES: Record<RouteName, PageDef> = {
  [ROUTES.HOME]: { open: "/" },
  [ROUTES.PLATFORMS_INDEX]: { open: "/platforms" },
  [ROUTES.PLATFORM]: { open: gotoFirstPlatform },
  [ROUTES.COLLECTIONS_INDEX]: { open: "/collections" },
  [ROUTES.SEARCH]: { open: "/search" },
  [ROUTES.MUSIC]: { open: "/music" },
  [ROUTES.ROM]: { open: clickThroughToFirstRom },
  [ROUTES.SCAN]: { open: "/scan" },
  [ROUTES.UPLOAD]: { open: "/upload" },
  [ROUTES.ACTIVITY]: { open: "/activity" },
  [ROUTES.NOTIFICATIONS]: { open: "/notifications" },
  [ROUTES.USER_PROFILE]: { open: gotoOwnProfile },
  [ROUTES.USER_INTERFACE]: { open: "/user-interface" },
  [ROUTES.LIBRARY_MANAGEMENT]: { open: "/library-management" },
  [ROUTES.SCAN_SETTINGS]: { open: "/scan-settings" },
  [ROUTES.CONVERSION_SETTINGS]: { open: "/conversion-settings" },
  [ROUTES.METADATA_SOURCES]: { open: "/metadata-sources" },
  [ROUTES.CLIENT_API_TOKENS]: { open: "/client-api-tokens" },
  [ROUTES.DEVICES]: { open: "/devices" },
  [ROUTES.ADMINISTRATION]: { open: "/administration" },
  [ROUTES.SERVER_STATS]: { open: "/server-stats" },
  [ROUTES.LOGS]: { open: "/logs" },
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

// storageState is the field Playwright takes in test.use() and browser.newContext().
export type E2eSitemapEntry = {
  id: RouteName;
  path: string;
  tag: readonly E2eTag[];
} & Required<Pick<BrowserContextOptions, "storageState">>;

/** Every page with a fixed URL, with the session that opens it: what axe and
 *  lighthouse audit. Admin-only pages open as the admin, the rest as the viewer. */
export const E2E_SITEMAP: readonly E2eSitemapEntry[] = [
  {
    id: ROUTES.LOGIN,
    path: "/login",
    storageState: SIGNED_OUT,
    tag: [pageTag(ROUTES.LOGIN)],
  },
  ...(Object.entries(PAGES) as [RouteName, PageDef][]).flatMap(([id, def]) =>
    "open" in def && typeof def.open === "string"
      ? [
          {
            id,
            path: def.open,
            storageState: STORAGE_STATE[isAdminOnly(id) ? "admin" : "viewer"],
            tag: [pageTag(id)],
          },
        ]
      : [],
  ),
];
