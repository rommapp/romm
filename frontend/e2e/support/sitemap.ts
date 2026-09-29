import type { BrowserContextOptions } from "@playwright/test";
import { SIGNED_OUT, STORAGE_STATE } from "./auth";

// Every tag the suite uses, defined once.
export type E2eTag = typeof SMOKE | `@page:${string}`;

// Gates a merge. Spread it into the specific tests that belong in the gate,
// never onto a sitemap entry, or axe and lighthouse inherit it.
export const SMOKE = "@smoke";

// storageState is the field Playwright takes in test.use() and browser.newContext().
export type E2eSitemapEntry = {
  id: string;
  path: string;
  tag: readonly E2eTag[];
} & Required<Pick<BrowserContextOptions, "storageState">>;

// Every page reachable by a fixed URL. Pages that require click-through
// navigation to get an id (platform, gameDetails, profile) are not listed here.
export const E2E_SITEMAP = [
  {
    id: "login",
    path: "/login",
    storageState: SIGNED_OUT,
    tag: ["@page:login"],
  },
  {
    id: "home",
    path: "/",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:home"],
  },
  {
    id: "platforms",
    path: "/platforms",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:platforms"],
  },
  {
    id: "collections",
    path: "/collections",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:collections"],
  },
  {
    id: "search",
    path: "/search",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:search"],
  },
  {
    id: "music",
    path: "/music",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:music"],
  },
  {
    id: "scan",
    path: "/scan",
    storageState: STORAGE_STATE.admin,
    tag: ["@page:scan"],
  },
  {
    id: "upload",
    path: "/upload",
    storageState: STORAGE_STATE.admin,
    tag: ["@page:upload"],
  },
  {
    id: "activity",
    path: "/activity",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:activity"],
  },
  {
    id: "notifications",
    path: "/notifications",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:notifications"],
  },
  {
    id: "userInterface",
    path: "/user-interface",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:userInterface"],
  },
  {
    id: "libraryManagement",
    path: "/library-management",
    storageState: STORAGE_STATE.admin,
    tag: ["@page:libraryManagement"],
  },
  {
    id: "scanSettings",
    path: "/scan-settings",
    storageState: STORAGE_STATE.admin,
    tag: ["@page:scanSettings"],
  },
  {
    id: "metadataSources",
    path: "/metadata-sources",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:metadataSources"],
  },
  {
    id: "clientApiTokens",
    path: "/client-api-tokens",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:clientApiTokens"],
  },
  {
    id: "administration",
    path: "/administration",
    storageState: STORAGE_STATE.admin,
    tag: ["@page:administration"],
  },
  {
    id: "serverStats",
    path: "/server-stats",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:serverStats"],
  },
  {
    id: "logs",
    path: "/logs",
    storageState: STORAGE_STATE.admin,
    tag: ["@page:logs"],
  },
  {
    id: "controllerDebug",
    path: "/controller-debug",
    storageState: STORAGE_STATE.viewer,
    tag: ["@page:controllerDebug"],
  },
] as const satisfies readonly E2eSitemapEntry[];

// Lets a suite key per-page config (thresholds, blocking impacts) by id, so a
// typo or a removed page is a compile error.
export type E2eSitemapId = (typeof E2E_SITEMAP)[number]["id"];
