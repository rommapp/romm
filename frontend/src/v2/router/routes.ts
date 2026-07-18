// v2 Route Registry
//
// As each wave migrates a view to v2, add its lazy-imported component here
// under the matching route name. The main router (src/plugins/router.ts)
// injects these into the v1 route config as Vue Router named views:
//
//   components: { default: v1Component, v2: v2RouteComponents[name] }
//
// When the user's uiVersion is "v2" the named <router-view name="v2"> in the
// v2 AppLayout renders the v2 component. Routes without a v2 entry fall
// through to the `fallbackComponent` so the user sees a helpful "not ready
// yet" screen instead of a blank page.
//
// NOTE: We use string keys instead of importing ROUTES from @/plugins/router
// to avoid a circular import (router.ts ↔ v2/router/routes.ts). Keys here
// MUST match the string values in the ROUTES constant in plugins/router.ts.
import type { Component } from "vue";

export type V2Route = () => Promise<Component>;

export const v2RouteComponents: Partial<Record<string, V2Route>> = {
  home: () => import("@/v2/views/Home.vue"),
  activity: () => import("@/v2/views/Activity.vue"),
  // Wave 1 — Auth flows
  login: () => import("@/v2/views/Auth/Login.vue"),
  "reset-password": () => import("@/v2/views/Auth/ResetPassword.vue"),
  register: () => import("@/v2/views/Auth/Register.vue"),
  setup: () => import("@/v2/views/Auth/Setup.vue"),
  // Wave 3 — Gallery
  platform: () => import("@/v2/views/Gallery/Platform.vue"),
  search: () => import("@/v2/views/Gallery/Search.vue"),
  collection: () => import("@/v2/views/Gallery/Collection.vue"),
  "virtual-collection": () => import("@/v2/views/Gallery/Collection.vue"),
  "smart-collection": () => import("@/v2/views/Gallery/Collection.vue"),
  // Wave 4 — Game details
  rom: () => import("@/v2/views/GameDetails.vue"),
  // Wave 5 — Players
  emulatorjs: () => import("@/v2/views/Player/EmulatorJS.vue"),
  ruffle: () => import("@/v2/views/Player/Ruffle.vue"),
  // Wave 6 — Library Tools (Scan / Upload) + Pair
  scan: () => import("@/v2/views/Scan.vue"),
  upload: () => import("@/v2/views/Upload.vue"),
  // Pair is wired via a top-level PairDispatcher (see plugins/router.ts); no
  // named-view entry is needed — the dispatcher picks v1 or v2 itself.
  // Wave 7 — Settings suite
  "user-profile": () => import("@/v2/views/Settings/UserProfile.vue"),
  "user-interface": () => import("@/v2/views/Settings/UserInterface.vue"),
  "library-management": () =>
    import("@/v2/views/Settings/LibraryManagement.vue"),
  "metadata-sources": () => import("@/v2/views/Settings/MetadataSources.vue"),
  "client-api-tokens": () => import("@/v2/views/Settings/ClientApiTokens.vue"),
  administration: () => import("@/v2/views/Settings/Administration.vue"),
  "server-stats": () => import("@/v2/views/Settings/ServerStats.vue"),
  logs: () => import("@/v2/views/Settings/Logs.vue"),
  // V2-only index pages (no v1 equivalent — the v1 UI uses its drawer)
  "platforms-index": () => import("@/v2/views/PlatformsIndex.vue"),
  "collections-index": () => import("@/v2/views/CollectionsIndex.vue"),
  // V2-only dev tool — live gamepad input inspector.
  "controller-debug": () => import("@/v2/views/ControllerDebug.vue"),
};

export const fallbackComponent: V2Route = () =>
  import("@/v2/views/NotReady.vue");

export const v2Layouts = {
  main: () => import("@/v2/layouts/AppLayout.vue"),
  auth: () => import("@/v2/layouts/AuthLayout.vue"),
  // Sub-layouts mounted inside AppLayout via grouping parent routes.
  // Each owns a section's chrome (sidebar / hero / etc.) and renders
  // the active child via `<router-view name="v2" />`.
  settings: () => import("@/v2/layouts/SettingsLayout.vue"),
  // Tiny `<router-view />` shim used as the `default` (v1) named-view
  // target on those v2-only grouping parents — v1 doesn't share their
  // chrome so it just forwards down to the child's v1 component.
  // @deprecated v2: delete with v1 (see Passthrough.vue).
  passthrough: () => import("@/v2/layouts/Passthrough.vue"),
};
