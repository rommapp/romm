// Route Registry
//
// Lazy-imported view components keyed by route name. The main router
// (src/plugins/router.ts) looks each route up here; a name without an entry
// falls through to `notFoundComponent`.
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
  // Wave 1: Auth flows
  [ROUTES.LOGIN]: () => import("@/v2/views/Auth/Login.vue"),
  [ROUTES.RESET_PASSWORD]: () => import("@/v2/views/Auth/ResetPassword.vue"),
  [ROUTES.REGISTER]: () => import("@/v2/views/Auth/Register.vue"),
  [ROUTES.SETUP]: () => import("@/v2/views/Auth/Setup.vue"),
  // Wave 3: Gallery
  [ROUTES.PLATFORM]: () => import("@/v2/views/Gallery/Platform.vue"),
  [ROUTES.SEARCH]: () => import("@/v2/views/Gallery/Search.vue"),
  [ROUTES.MUSIC]: () => import("@/v2/views/Jukebox/index.vue"),
  [ROUTES.COLLECTION]: () => import("@/v2/views/Gallery/Collection.vue"),
  [ROUTES.VIRTUAL_COLLECTION]: () =>
    import("@/v2/views/Gallery/Collection.vue"),
  [ROUTES.SMART_COLLECTION]: () => import("@/v2/views/Gallery/Collection.vue"),
  // Wave 4: Game details
  [ROUTES.ROM]: () => import("@/v2/views/GameDetails.vue"),
  // Wave 5: Players
  [ROUTES.EMULATORJS]: () => import("@/v2/views/Player/EmulatorJS.vue"),
  [ROUTES.JSDOS]: () => import("@/v2/views/Player/JsDos.vue"),
  [ROUTES.PICO8]: () => import("@/v2/views/Player/Pico8.vue"),
  [ROUTES.EASYRPG]: () => import("@/v2/views/Player/EasyRpg.vue"),
  [ROUTES.RUFFLE]: () => import("@/v2/views/Player/Ruffle.vue"),
  [ROUTES.STREAM]: () => import("@/v2/views/Player/Stream.vue"),
  [ROUTES.STREAM_DESKTOP]: () => import("@/v2/views/Player/Desktop.vue"),
  // Wave 6: Library Tools (Scan / Upload) + Pair
  [ROUTES.SCAN]: () => import("@/v2/views/Scan.vue"),
  [ROUTES.UPLOAD]: () => import("@/v2/views/Upload.vue"),
  [ROUTES.PAIR]: () => import("@/v2/views/PairShell.vue"),
  // Wave 7: Settings suite
  [ROUTES.USER_PROFILE]: () => import("@/v2/views/Settings/UserProfile.vue"),
  [ROUTES.USER_INTERFACE]: () =>
    import("@/v2/views/Settings/UserInterface.vue"),
  [ROUTES.LIBRARY_MANAGEMENT]: () =>
    import("@/v2/views/Settings/LibraryManagement.vue"),
  [ROUTES.SCAN_SETTINGS]: () => import("@/v2/views/Settings/ScanSettings.vue"),
  [ROUTES.CONVERSION_SETTINGS]: () =>
    import("@/v2/views/Settings/ConversionSettings.vue"),
  [ROUTES.METADATA_SOURCES]: () =>
    import("@/v2/views/Settings/MetadataSources.vue"),
  [ROUTES.CLIENT_API_TOKENS]: () =>
    import("@/v2/views/Settings/ClientApiTokens.vue"),
  [ROUTES.DEVICES]: () => import("@/v2/views/Settings/Devices.vue"),
  [ROUTES.ADMINISTRATION]: () =>
    import("@/v2/views/Settings/Administration.vue"),
  [ROUTES.SERVER_STATS]: () => import("@/v2/views/Settings/ServerStats.vue"),
  [ROUTES.LOGS]: () => import("@/v2/views/Settings/Logs.vue"),
  [ROUTES.PLATFORMS_INDEX]: () => import("@/v2/views/PlatformsIndex.vue"),
  [ROUTES.COLLECTIONS_INDEX]: () => import("@/v2/views/CollectionsIndex.vue"),
  // Dev tool: live gamepad input inspector.
  [ROUTES.CONTROLLER_DEBUG]: () => import("@/v2/views/ControllerDebug.vue"),
};

export const v2Layouts = {
  main: () => import("@/v2/layouts/AppLayout.vue"),
  auth: () => import("@/v2/layouts/AuthLayout.vue"),
  // Sub-layouts mounted inside AppLayout via grouping parent routes.
  // Each owns a section's chrome (sidebar / hero / etc.) and renders
  // the active child via `<router-view />`.
  settings: () => import("@/v2/layouts/SettingsLayout.vue"),
};
