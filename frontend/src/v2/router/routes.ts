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
// through to `notFoundComponent`, which is correct now that every route the
// v2 UI links to is migrated: an unregistered name leads nowhere in v2.
import type { Component } from "vue";
import { ROUTES, type RouteName } from "@/plugins/routeNames";

export type V2Route = () => Promise<Component>;

// Rendered for the catch-all route and for any route name that reaches
// `v2For` without an entry below.
export const notFoundComponent: V2Route = () =>
  import("@/v2/views/NotFound.vue");

export const v2RouteComponents: Partial<Record<RouteName, V2Route>> = {
  [ROUTES.HOME]: () => import("@/v2/views/Home.vue"),
  [ROUTES.ACTIVITY]: () => import("@/v2/views/Activity.vue"),
  [ROUTES.NOTIFICATIONS]: () => import("@/v2/views/Notifications.vue"),
  // Wave 1 — Auth flows
  [ROUTES.LOGIN]: () => import("@/v2/views/Auth/Login.vue"),
  [ROUTES.RESET_PASSWORD]: () => import("@/v2/views/Auth/ResetPassword.vue"),
  [ROUTES.REGISTER]: () => import("@/v2/views/Auth/Register.vue"),
  [ROUTES.SETUP]: () => import("@/v2/views/Auth/Setup.vue"),
  // Wave 3 — Gallery
  [ROUTES.PLATFORM]: () => import("@/v2/views/Gallery/Platform.vue"),
  [ROUTES.SEARCH]: () => import("@/v2/views/Gallery/Search.vue"),
  [ROUTES.MUSIC]: () => import("@/v2/views/Jukebox/index.vue"),
  [ROUTES.COLLECTION]: () => import("@/v2/views/Gallery/Collection.vue"),
  [ROUTES.VIRTUAL_COLLECTION]: () =>
    import("@/v2/views/Gallery/Collection.vue"),
  [ROUTES.SMART_COLLECTION]: () => import("@/v2/views/Gallery/Collection.vue"),
  // Wave 4 — Game details
  [ROUTES.ROM]: () => import("@/v2/views/GameDetails.vue"),
  // Wave 5 — Players
  [ROUTES.EMULATORJS]: () => import("@/v2/views/Player/EmulatorJS.vue"),
  [ROUTES.JSDOS]: () => import("@/v2/views/Player/JsDos.vue"),
  [ROUTES.PICO8]: () => import("@/v2/views/Player/Pico8.vue"),
  [ROUTES.RUFFLE]: () => import("@/v2/views/Player/Ruffle.vue"),
  [ROUTES.STREAM]: () => import("@/v2/views/Player/Stream.vue"),
  [ROUTES.STREAM_DESKTOP]: () => import("@/v2/views/Player/Desktop.vue"),
  // Wave 6 — Library Tools (Scan / Upload) + Pair
  [ROUTES.SCAN]: () => import("@/v2/views/Scan.vue"),
  [ROUTES.UPLOAD]: () => import("@/v2/views/Upload.vue"),
  // Pair is wired via a top-level PairDispatcher (see plugins/router.ts); no
  // named-view entry is needed — the dispatcher picks v1 or v2 itself.
  // Wave 7 — Settings suite
  [ROUTES.USER_PROFILE]: () => import("@/v2/views/Settings/UserProfile.vue"),
  [ROUTES.USER_INTERFACE]: () =>
    import("@/v2/views/Settings/UserInterface.vue"),
  [ROUTES.LIBRARY_MANAGEMENT]: () =>
    import("@/v2/views/Settings/LibraryManagement.vue"),
  [ROUTES.SCAN_SETTINGS]: () => import("@/v2/views/Settings/ScanSettings.vue"),
  [ROUTES.METADATA_SOURCES]: () =>
    import("@/v2/views/Settings/MetadataSources.vue"),
  [ROUTES.CLIENT_API_TOKENS]: () =>
    import("@/v2/views/Settings/ClientApiTokens.vue"),
  [ROUTES.ADMINISTRATION]: () =>
    import("@/v2/views/Settings/Administration.vue"),
  [ROUTES.SERVER_STATS]: () => import("@/v2/views/Settings/ServerStats.vue"),
  [ROUTES.LOGS]: () => import("@/v2/views/Settings/Logs.vue"),
  // V2-only index pages (no v1 equivalent — the v1 UI uses its drawer)
  [ROUTES.PLATFORMS_INDEX]: () => import("@/v2/views/PlatformsIndex.vue"),
  [ROUTES.COLLECTIONS_INDEX]: () => import("@/v2/views/CollectionsIndex.vue"),
  // V2-only dev tool — live gamepad input inspector.
  [ROUTES.CONTROLLER_DEBUG]: () => import("@/v2/views/ControllerDebug.vue"),
  // v1-only easter egg: no v2 component links here, so the URL is a dead end.
  [ROUTES.APRIL_FOOLS]: notFoundComponent,
};

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
