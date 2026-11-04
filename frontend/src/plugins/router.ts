import { storeToRefs } from "pinia";
import { watch } from "vue";
import {
  createRouter,
  createWebHistory,
  type NavigationGuardWithThis,
  type RouteLocationNormalized,
} from "vue-router";
import { DEFAULT_TITLE } from "@/composables/usePageTitle";
import i18n, { loadLocale } from "@/locales";
import {
  isAuthExemptRoute,
  ROUTE_SCOPES,
  ROUTES,
  type RouteName,
} from "@/plugins/routeNames";
import { startViewTransition } from "@/plugins/transition";
import {
  notFoundComponent,
  routeLayouts,
  routeComponents,
} from "@/router/routes";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import type { User } from "@/stores/users";

export { isAuthExemptRoute, ROUTES };

// Resolve the component for a given route name, falling back to the 404 view
// so every route renders something.
function routeComponent(routeName: RouteName) {
  const component = routeComponents[routeName];
  if (!component && import.meta.env.DEV) {
    console.warn(`[v2] route "${routeName}" has no v2 component; showing 404`);
  }
  return component ?? notFoundComponent;
}

const routes = [
  {
    path: "/setup",
    component: routeLayouts.auth,
    children: [
      {
        path: "",
        name: ROUTES.SETUP,
        meta: {
          title: "login.setup-wizard",
        },
        component: routeComponent(ROUTES.SETUP),
      },
    ],
  },
  {
    path: "/login",
    component: routeLayouts.auth,
    children: [
      {
        path: "",
        name: ROUTES.LOGIN,
        meta: {
          title: "login.login",
        },
        component: routeComponent(ROUTES.LOGIN),
      },
    ],
  },
  {
    path: "/reset-password",
    component: routeLayouts.auth,
    children: [
      {
        path: "",
        name: ROUTES.RESET_PASSWORD,
        meta: {
          title: "login.reset-password",
        },
        component: routeComponent(ROUTES.RESET_PASSWORD),
      },
    ],
  },
  {
    path: "/register",
    component: routeLayouts.auth,
    children: [
      {
        path: "",
        name: ROUTES.REGISTER,
        meta: {
          title: "login.register",
        },
        component: routeComponent(ROUTES.REGISTER),
      },
    ],
  },
  {
    path: "/",
    name: ROUTES.MAIN,
    component: routeLayouts.main,
    children: [
      {
        path: "",
        name: ROUTES.HOME,
        meta: {
          title: "settings.home",
        },
        component: routeComponent(ROUTES.HOME),
      },
      {
        path: "search",
        name: ROUTES.SEARCH,
        meta: {
          title: "common.search",
        },
        component: routeComponent(ROUTES.SEARCH),
      },
      {
        path: "music/:mode?",
        name: ROUTES.MUSIC,
        meta: { title: "common.jukebox" },
        component: routeComponent(ROUTES.MUSIC),
      },
      {
        path: "platform/:platform",
        name: ROUTES.PLATFORM,
        component: routeComponent(ROUTES.PLATFORM),
      },
      {
        path: "collection/:collection",
        name: ROUTES.COLLECTION,
        component: routeComponent(ROUTES.COLLECTION),
      },
      {
        path: "collection/virtual/:collection",
        name: ROUTES.VIRTUAL_COLLECTION,
        component: routeComponent(ROUTES.VIRTUAL_COLLECTION),
      },
      {
        path: "collection/smart/:collection",
        name: ROUTES.SMART_COLLECTION,
        component: routeComponent(ROUTES.SMART_COLLECTION),
      },
      {
        path: "rom/:rom",
        name: ROUTES.ROM,
        component: routeComponent(ROUTES.ROM),
        beforeEnter: (async (to, _from, next) => {
          const romsStore = storeRoms();

          // Read the ROM on every entry, a matching id included: a play page
          // writes saves server-side, then navigates here to hand the tab back.
          try {
            const data = await romApi.getRom({
              romId: parseInt(to.params.rom as string),
            });
            romsStore.setCurrentRom(data.data);
          } catch (error) {
            console.error(error);
          }
          next();
        }) as NavigationGuardWithThis<undefined>,
      },
      {
        path: "rom/:rom/ejs",
        name: ROUTES.EMULATORJS,
        component: routeComponent(ROUTES.EMULATORJS),
      },
      {
        path: "rom/:rom/jsdos",
        name: ROUTES.JSDOS,
        component: routeComponent(ROUTES.JSDOS),
      },
      {
        path: "rom/:rom/pico8",
        name: ROUTES.PICO8,
        component: routeComponent(ROUTES.PICO8),
      },
      {
        path: "rom/:rom/easyrpg",
        name: ROUTES.EASYRPG,
        component: routeComponent(ROUTES.EASYRPG),
      },
      {
        path: "rom/:rom/ruffle",
        name: ROUTES.RUFFLE,
        component: routeComponent(ROUTES.RUFFLE),
      },
      {
        path: "rom/:rom/stream",
        name: ROUTES.STREAM,
        component: routeComponent(ROUTES.STREAM),
      },
      {
        // No :rom, unlike the player route: a desktop session runs no game.
        // The container is a query param because its key is a URL.
        path: "stream/desktop",
        name: ROUTES.STREAM_DESKTOP,
        component: routeComponent(ROUTES.STREAM_DESKTOP),
      },
      // Settings group: every settings route shares the same sub-layout
      // (sidebar + content panel). Library Tools (Scan / Upload / Patcher)
      // live here too so they share the settings sidebar shell.
      {
        path: "",
        component: routeLayouts.settings,
        children: [
          {
            path: "scan",
            name: ROUTES.SCAN,
            meta: {
              title: "scan.scan",
              bare: true,
            },
            component: routeComponent(ROUTES.SCAN),
          },
          {
            path: "upload",
            name: ROUTES.UPLOAD,
            meta: {
              title: "common.upload-roms",
              fill: "desktop",
            },
            component: routeComponent(ROUTES.UPLOAD),
          },
          {
            path: "activity",
            name: ROUTES.ACTIVITY,
            meta: {
              title: "activity.active-sessions",
              bare: true,
            },
            component: routeComponent(ROUTES.ACTIVITY),
          },
          {
            path: "notifications",
            name: ROUTES.NOTIFICATIONS,
            meta: {
              title: "notifications.notifications",
              bare: true,
            },
            component: routeComponent(ROUTES.NOTIFICATIONS),
          },
          {
            path: "user/:user",
            name: ROUTES.USER_PROFILE,
            meta: { bare: true },
            component: routeComponent(ROUTES.USER_PROFILE),
          },
          {
            path: "user-interface",
            name: ROUTES.USER_INTERFACE,
            meta: {
              title: "common.user-interface",
              bare: true,
            },
            component: routeComponent(ROUTES.USER_INTERFACE),
          },
          {
            path: "library-management",
            name: ROUTES.LIBRARY_MANAGEMENT,
            meta: {
              title: "common.library-management",
              bare: true,
            },
            component: routeComponent(ROUTES.LIBRARY_MANAGEMENT),
          },
          {
            path: "scan-settings",
            name: ROUTES.SCAN_SETTINGS,
            meta: {
              title: "settings.scan-settings",
              bare: true,
            },
            component: routeComponent(ROUTES.SCAN_SETTINGS),
          },
          {
            path: "conversion-settings",
            name: ROUTES.CONVERSION_SETTINGS,
            meta: {
              title: "settings.conversion-settings",
              bare: true,
            },
            component: routeComponent(ROUTES.CONVERSION_SETTINGS),
          },
          {
            path: "metadata-sources",
            name: ROUTES.METADATA_SOURCES,
            meta: {
              title: "scan.metadata-sources",
              bare: true,
            },
            component: routeComponent(ROUTES.METADATA_SOURCES),
          },
          {
            path: "client-api-tokens",
            name: ROUTES.CLIENT_API_TOKENS,
            meta: {
              title: "settings.client-api-tokens",
              bare: true,
            },
            component: routeComponent(ROUTES.CLIENT_API_TOKENS),
          },
          {
            path: "devices",
            name: ROUTES.DEVICES,
            meta: {
              title: "settings.devices",
              bare: true,
            },
            component: routeComponent(ROUTES.DEVICES),
          },
          {
            path: "administration",
            name: ROUTES.ADMINISTRATION,
            meta: {
              title: "common.administration",
              bare: true,
            },
            component: routeComponent(ROUTES.ADMINISTRATION),
          },
          {
            path: "server-stats",
            name: ROUTES.SERVER_STATS,
            meta: {
              title: "common.server-stats",
              bare: true,
            },
            component: routeComponent(ROUTES.SERVER_STATS),
          },
          {
            path: "logs",
            name: ROUTES.LOGS,
            meta: {
              title: "common.logs",
              bare: true,
              // The log panel fills the viewport and scrolls internally
              // instead of growing the document: see SettingsLayout `fill`.
              fill: true,
            },
            component: routeComponent(ROUTES.LOGS),
          },
          {
            // Controller-debug lives outside the Settings sidebar
            // but reuses the same chrome (sidebar layout + bare
            // body) so the input system inspector reads as another
            // settings-adjacent tool rather than a standalone view.
            path: "controller-debug",
            name: ROUTES.CONTROLLER_DEBUG,
            meta: { title: "settings.controller-debug", bare: true },
            component: routeComponent(ROUTES.CONTROLLER_DEBUG),
          },
        ],
      },
      {
        path: "platforms",
        name: ROUTES.PLATFORMS_INDEX,
        meta: { title: "common.platforms" },
        component: routeComponent(ROUTES.PLATFORMS_INDEX),
      },
      {
        path: "collections",
        name: ROUTES.COLLECTIONS_INDEX,
        meta: { title: "common.collections" },
        component: routeComponent(ROUTES.COLLECTIONS_INDEX),
      },
      {
        path: ":pathMatch(.*)*",
        name: ROUTES.NOT_FOUND,
        component: notFoundComponent,
      },
    ],
  },
  {
    path: "/pair/device",
    name: ROUTES.PAIR_DEVICE,
    component: () => import("@/views/DevicePairShell.vue"),
  },
  {
    path: "/pair",
    name: ROUTES.PAIR,
    component: routeComponent(ROUTES.PAIR),
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // popstate (back/forward): restore the saved offset.
    if (savedPosition) return savedPosition;
    // Same path → only query/hash changed (e.g., the v2 GameDetails
    // tab/subtab params, gallery filter syncs). The user's view should
    // stay where it is; scrolling to top would make the URL update
    // visible as a UX jump.
    if (to.path === from.path) return false;
    // Genuine route change: start fresh from the top.
    return { left: 0, top: 0 };
  },
});

function checkRoutePermissions(route: string, user: User | null): boolean {
  // No checks needed for login and setup pages
  if (isAuthExemptRoute(route)) {
    return true;
  }

  // No user, no access
  if (!user) return false;

  const requiredScopes = ROUTE_SCOPES[route as RouteName] ?? [];
  return requiredScopes.every((scope) => user.oauth_scopes.includes(scope));
}

// `meta.title` holds an i18n key, translated per navigation rather than when
// the route table is built. Messages load asynchronously and aren't there yet
// at module-eval time.
export function applyRouteTitle(
  route: RouteLocationNormalized,
  from?: RouteLocationNormalized,
) {
  if (route.meta.title) {
    document.title = i18n.global.t(route.meta.title as string);
    return;
  }
  // A query/hash-only navigation leaves the view mounted, so `usePageTitle`
  // won't refire and the fallback would drop the title it already set.
  if (from && route.path === from.path) return;
  document.title = DEFAULT_TITLE;
}

router.beforeEach((to, from, next) => {
  const heartbeat = storeHeartbeat();
  const auth = storeAuth();
  const { user } = storeToRefs(auth);
  const currentRoute = to.name?.toString();

  try {
    // Backend unreachable/broken: we can't trust the setup/auth state, and
    // bouncing to /login would just strand the user on a page that can't work
    // either. Let them stay on (and navigate within) whatever the cached state
    // allows; the offline notice explains it and the connection layer
    // re-routes correctly once the backend answers again.
    if (!heartbeat.connected) {
      applyRouteTitle(to, from);
      return next();
    }

    // Handle setup wizard
    if (heartbeat.value.SYSTEM.SHOW_SETUP_WIZARD) {
      return currentRoute !== "setup" ? next({ name: ROUTES.SETUP }) : next();
    }

    // Handle authentication: unauth'd users visiting a non-exempt route
    // land on /login. Without this branch, they fall through to the
    // permission check below, fail it, get redirected to the catch-all 404
    // (which matches /), and the guard re-runs forever.
    if (!user.value && (!currentRoute || !isAuthExemptRoute(currentRoute))) {
      return next({
        name: ROUTES.LOGIN,
        query: {
          next: to.query.next ?? to.fullPath,
        },
      });
    }

    // SHOW_SETUP_WIZARD is false here, so setup is already done: nobody
    // belongs on /setup anymore. `/setup` is auth-exempt (so the block above
    // won't bounce an unauthenticated visitor), so redirect both cases:
    // authenticated users go home, everyone else to login. Without covering
    // the unauth case, a stale link / manual nav to /setup would strand the
    // user on the wizard, whose API then 403s once an admin exists.
    if (currentRoute === ROUTES.SETUP) {
      return next({ name: user.value ? ROUTES.HOME : ROUTES.LOGIN });
    }

    // Check permissions
    if (currentRoute && !checkRoutePermissions(currentRoute, user.value)) {
      return next({ name: ROUTES.NOT_FOUND });
    }

    // DISABLE_LOGS_VIEWER takes the log tab away; an admin still has the
    // event log there, anyone else has nothing left on the page.
    if (
      currentRoute === ROUTES.LOGS &&
      heartbeat.value.FRONTEND.DISABLE_LOGS_VIEWER &&
      user.value?.role !== "admin"
    ) {
      return next({ name: ROUTES.NOT_FOUND });
    }

    applyRouteTitle(to, from);
    next();
  } catch (error) {
    console.error("Navigation guard error:", error);
    document.title = DEFAULT_TITLE;
    next({ name: ROUTES.LOGIN });
  }
});

// The stored language is applied when the app mounts, after the first
// navigation has already resolved the title in the default locale. Routes
// whose view owns its title (usePageTitle) carry no `meta.title` and keep it.
watch(i18n.global.locale, async (locale) => {
  await loadLocale(locale);
  const route = router.currentRoute.value;
  if (route.meta.title) applyRouteTitle(route);
});

router.beforeResolve(async (to, from) => {
  // Query/hash-only changes (same path: e.g. the v2 GameDetails `?tab=`
  // param) aren't a real view change. Running a view transition would
  // snapshot every `view-transition-name` element (like the details cover)
  // into the browser's top layer for the crossfade, briefly floating it over
  // the fixed navbar. Skip them: matching `scrollBehavior` above.
  if (to.path === from.path) return;
  const viewTransition = startViewTransition();
  await viewTransition.captured;
});

export default router;
