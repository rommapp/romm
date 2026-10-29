// Route Registry
//
// Lazy-imported view components keyed by route name. The main router
// (src/plugins/router.ts) looks each route up here; a name without an entry
// falls through to `notFoundComponent`.
import type { Component } from "vue";
import { ROUTES, type RouteName } from "@/plugins/routeNames";

export type RouteViewLoader = () => Promise<Component>;

// Rendered for the catch-all route and for any route name that reaches
// `routeComponent` without an entry below.
export const notFoundComponent: RouteViewLoader = () =>
  import("@/views/NotFound.vue");

export const routeComponents: Partial<Record<RouteName, RouteViewLoader>> = {
  [ROUTES.HOME]: () => import("@/views/Home.vue"),
  [ROUTES.ACTIVITY]: () => import("@/views/Activity.vue"),
  [ROUTES.NOTIFICATIONS]: () => import("@/views/Notifications.vue"),
  // Wave 1: Auth flows
  [ROUTES.LOGIN]: () => import("@/views/Auth/Login.vue"),
  [ROUTES.RESET_PASSWORD]: () => import("@/views/Auth/ResetPassword.vue"),
  [ROUTES.REGISTER]: () => import("@/views/Auth/Register.vue"),
  [ROUTES.SETUP]: () => import("@/views/Auth/Setup.vue"),
  // Wave 3: Gallery
  [ROUTES.PLATFORM]: () => import("@/views/Gallery/Platform.vue"),
  [ROUTES.SEARCH]: () => import("@/views/Gallery/Search.vue"),
  [ROUTES.MUSIC]: () => import("@/views/Jukebox/index.vue"),
  [ROUTES.COLLECTION]: () => import("@/views/Gallery/Collection.vue"),
  [ROUTES.VIRTUAL_COLLECTION]: () => import("@/views/Gallery/Collection.vue"),
  [ROUTES.SMART_COLLECTION]: () => import("@/views/Gallery/Collection.vue"),
  // Wave 4: Game details
  [ROUTES.ROM]: () => import("@/views/GameDetails.vue"),
  // Wave 5: Players
  [ROUTES.EMULATORJS]: () => import("@/views/Player/EmulatorJS.vue"),
  [ROUTES.JSDOS]: () => import("@/views/Player/JsDos.vue"),
  [ROUTES.PICO8]: () => import("@/views/Player/Pico8.vue"),
  [ROUTES.EASYRPG]: () => import("@/views/Player/EasyRpg.vue"),
  [ROUTES.RUFFLE]: () => import("@/views/Player/Ruffle.vue"),
  [ROUTES.STREAM]: () => import("@/views/Player/Stream.vue"),
  [ROUTES.STREAM_DESKTOP]: () => import("@/views/Player/Desktop.vue"),
  // Wave 6: Library Tools (Scan / Upload) + Pair
  [ROUTES.SCAN]: () => import("@/views/Scan.vue"),
  [ROUTES.UPLOAD]: () => import("@/views/Upload.vue"),
  [ROUTES.PAIR]: () => import("@/views/PairShell.vue"),
  // Wave 7: Settings suite
  [ROUTES.USER_PROFILE]: () => import("@/views/Settings/UserProfile.vue"),
  [ROUTES.USER_INTERFACE]: () => import("@/views/Settings/UserInterface.vue"),
  [ROUTES.LIBRARY_MANAGEMENT]: () =>
    import("@/views/Settings/LibraryManagement.vue"),
  [ROUTES.SCAN_SETTINGS]: () => import("@/views/Settings/ScanSettings.vue"),
  [ROUTES.CONVERSION_SETTINGS]: () =>
    import("@/views/Settings/ConversionSettings.vue"),
  [ROUTES.METADATA_SOURCES]: () =>
    import("@/views/Settings/MetadataSources.vue"),
  [ROUTES.CLIENT_API_TOKENS]: () =>
    import("@/views/Settings/ClientApiTokens.vue"),
  [ROUTES.DEVICES]: () => import("@/views/Settings/Devices.vue"),
  [ROUTES.ADMINISTRATION]: () => import("@/views/Settings/Administration.vue"),
  [ROUTES.SERVER_STATS]: () => import("@/views/Settings/ServerStats.vue"),
  [ROUTES.LOGS]: () => import("@/views/Settings/Logs.vue"),
  [ROUTES.PLATFORMS_INDEX]: () => import("@/views/PlatformsIndex.vue"),
  [ROUTES.COLLECTIONS_INDEX]: () => import("@/views/CollectionsIndex.vue"),
  // Dev tool: live gamepad input inspector.
  [ROUTES.CONTROLLER_DEBUG]: () => import("@/views/ControllerDebug.vue"),
};

export const routeLayouts = {
  main: () => import("@/layouts/AppLayout.vue"),
  auth: () => import("@/layouts/AuthLayout.vue"),
  // Sub-layouts mounted inside AppLayout via grouping parent routes.
  // Each owns a section's chrome (sidebar / hero / etc.) and renders
  // the active child via `<router-view />`.
  settings: () => import("@/layouts/SettingsLayout.vue"),
};
