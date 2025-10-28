import { storeToRefs } from "pinia";
import {
  createRouter,
  createWebHistory,
  type NavigationGuardWithThis,
} from "vue-router";
import i18n from "@/locales";
import { startViewTransition } from "@/plugins/transition";
import romApi from "@/services/api/rom";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import storeRoms from "@/stores/roms";
import type { User } from "@/stores/users";

export const ROUTES = {
  SETUP: "setup",
  LOGIN: "login",
  RESET_PASSWORD: "reset-password",
  REGISTER: "register",
  MAIN: "main",
  HOME: "home",
  SEARCH: "search",
  PLATFORM: "platform",
  COLLECTION: "collection",
  VIRTUAL_COLLECTION: "virtual-collection",
  SMART_COLLECTION: "smart-collection",
  ROM: "rom",
  EMULATORJS: "emulatorjs",
  RUFFLE: "ruffle",
  SCAN: "scan",
  USER_PROFILE: "user-profile",
  USER_INTERFACE: "user-interface",
  LIBRARY_MANAGEMENT: "library-management",
  METADATA_SOURCES: "metadata-sources",
  ADMINISTRATION: "administration",
  SERVER_STATS: "server-stats",
  NOT_FOUND: "404",
  CONSOLE_HOME: "console-home",
  CONSOLE_PLATFORM: "console-platform",
  CONSOLE_COLLECTION: "console-collection",
  CONSOLE_SMART_COLLECTION: "console-smart-collection",
  CONSOLE_VIRTUAL_COLLECTION: "console-virtual-collection",
  CONSOLE_ROM: "console-rom",
  CONSOLE_PLAY: "console-play",
} as const;

const routes = [
  {
    path: "/setup",
    component: () => import("@/layouts/Auth.vue"),
    children: [
      {
        path: "",
        name: ROUTES.SETUP,
        meta: {
          title: i18n.global.t("login.setup-wizard"),
        },
        component: () => import("@/views/Auth/Setup.vue"),
      },
    ],
  },
  {
    path: "/login",
    component: () => import("@/layouts/Auth.vue"),
    children: [
      {
        path: "",
        name: ROUTES.LOGIN,
        meta: {
          title: i18n.global.t("login.login"),
        },
        component: () => import("@/views/Auth/Login.vue"),
      },
    ],
  },
  {
    path: "/reset-password",
    component: () => import("@/layouts/Auth.vue"),
    children: [
      {
        path: "",
        name: ROUTES.RESET_PASSWORD,
        meta: {
          title: i18n.global.t("login.reset-password"),
        },
        component: () => import("@/views/Auth/ResetPassword.vue"),
      },
    ],
  },
  {
    path: "/register",
    component: () => import("@/layouts/Auth.vue"),
    children: [
      {
        path: "",
        name: ROUTES.REGISTER,
        meta: {
          title: i18n.global.t("login.register"),
        },
        component: () => import("@/views/Auth/Register.vue"),
      },
    ],
  },
  {
    path: "/",
    name: ROUTES.MAIN,
    meta: {
      title: "RomM",
    },
    component: () => import("@/layouts/Main.vue"),
    children: [
      {
        path: "",
        name: ROUTES.HOME,
        meta: {
          title: i18n.global.t("settings.home"),
        },
        component: () => import("@/views/Home.vue"),
      },
      {
        path: "search",
        name: ROUTES.SEARCH,
        meta: {
          title: i18n.global.t("common.search"),
        },
        component: () => import("@/views/Gallery/Search.vue"),
      },
      {
        path: "platform/:platform",
        name: ROUTES.PLATFORM,
        component: () => import("@/views/Gallery/Platform.vue"),
      },
      {
        path: "collection/:collection",
        name: ROUTES.COLLECTION,
        component: () => import("@/views/Gallery/Collection/Collection.vue"),
      },
      {
        path: "collection/virtual/:collection",
        name: ROUTES.VIRTUAL_COLLECTION,
        component: () =>
          import("@/views/Gallery/Collection/VirtualCollection.vue"),
      },
      {
        path: "collection/smart/:collection",
        name: ROUTES.SMART_COLLECTION,
        component: () =>
          import("@/views/Gallery/Collection/SmartCollection.vue"),
      },
      {
        path: "rom/:rom",
        name: ROUTES.ROM,
        component: () => import("@/views/GameDetails.vue"),
        beforeEnter: (async (to, _from, next) => {
          const romsStore = storeRoms();

          if (
            !romsStore.currentRom ||
            romsStore.currentRom.id !== parseInt(to.params.rom as string)
          ) {
            try {
              const data = await romApi.getRom({
                romId: parseInt(to.params.rom as string),
              });
              romsStore.setCurrentRom(data.data);
            } catch (error) {
              console.error(error);
            }
          }
          next();
        }) as NavigationGuardWithThis<undefined>,
      },
      {
        path: "rom/:rom/ejs",
        name: ROUTES.EMULATORJS,
        component: () => import("@/views/Player/EmulatorJS/Base.vue"),
      },
      {
        path: "rom/:rom/ruffle",
        name: ROUTES.RUFFLE,
        component: () => import("@/views/Player/RuffleRS/Base.vue"),
      },
      {
        path: "scan",
        name: ROUTES.SCAN,
        meta: {
          title: i18n.global.t("scan.scan"),
        },
        component: () => import("@/views/Scan.vue"),
      },
      {
        path: "user/:user",
        name: ROUTES.USER_PROFILE,
        component: () => import("@/views/Settings/UserProfile.vue"),
      },
      {
        path: "user-interface",
        name: ROUTES.USER_INTERFACE,
        meta: {
          title: i18n.global.t("common.user-interface"),
        },
        component: () => import("@/views/Settings/UserInterface.vue"),
      },
      {
        path: "library-management",
        name: ROUTES.LIBRARY_MANAGEMENT,
        meta: {
          title: i18n.global.t("common.library-management"),
        },
        component: () => import("@/views/Settings/LibraryManagement.vue"),
      },
      {
        path: "metadata-sources",
        name: ROUTES.METADATA_SOURCES,
        meta: {
          title: i18n.global.t("scan.metadata-sources"),
        },
        component: () => import("@/views/Settings/MetadataSources.vue"),
      },
      {
        path: "administration",
        name: ROUTES.ADMINISTRATION,
        meta: {
          title: i18n.global.t("common.administration"),
        },
        component: () => import("@/views/Settings/Administration.vue"),
      },
      {
        path: "server-stats",
        name: ROUTES.SERVER_STATS,
        meta: {
          title: i18n.global.t("common.server-stats"),
        },
        component: () => import("@/views/Settings/ServerStats.vue"),
      },
      {
        path: ":pathMatch(.*)*",
        name: ROUTES.NOT_FOUND,
        component: () => import("@/views/404.vue"),
      },
    ],
  },
  // Console mode (separate UI namespace under /console)
  {
    path: "/console",
    component: () => import("@/console/Layout.vue"),
    children: [
      {
        path: "",
        name: ROUTES.CONSOLE_HOME,
        component: () => import("@/console/views/Home.vue"),
      },
      {
        path: "platform/:id",
        name: ROUTES.CONSOLE_PLATFORM,
        component: () => import("@/console/views/GamesList.vue"),
      },
      {
        path: "collection/:id",
        name: ROUTES.CONSOLE_COLLECTION,
        component: () => import("@/console/views/GamesList.vue"),
      },
      {
        path: "collection/smart/:id",
        name: ROUTES.CONSOLE_SMART_COLLECTION,
        component: () => import("@/console/views/GamesList.vue"),
      },
      {
        path: "collection/virtual/:id",
        name: ROUTES.CONSOLE_VIRTUAL_COLLECTION,
        component: () => import("@/console/views/GamesList.vue"),
      },
      {
        path: "rom/:rom",
        name: ROUTES.CONSOLE_ROM,
        component: () => import("@/console/views/Game.vue"),
      },
      {
        path: "rom/:rom/play",
        name: ROUTES.CONSOLE_PLAY,
        component: () => import("@/console/views/Play.vue"),
      },
    ],
  },
];

interface RoutePermissions {
  path: string;
  requiredScopes: string[];
}

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    // If savedPosition is available, it's a popstate navigation (back/forward)
    if (savedPosition) {
      return savedPosition;
    } else {
      // Otherwise, scroll to top
      return { left: 0, top: 0 };
    }
  },
});

const routePermissions: RoutePermissions[] = [
  { path: ROUTES.SCAN, requiredScopes: ["platforms.write"] },
  { path: ROUTES.LIBRARY_MANAGEMENT, requiredScopes: ["platforms.write"] },
  { path: ROUTES.ADMINISTRATION, requiredScopes: ["users.write"] },
];

function checkRoutePermissions(route: string, user: User | null): boolean {
  // No checks needed for login and setup pages
  if (
    route === ROUTES.LOGIN ||
    route === ROUTES.SETUP ||
    route === ROUTES.RESET_PASSWORD ||
    route === ROUTES.REGISTER
  )
    return true;

  // No user, no access
  if (!user) return false;

  // Check if route has permissions requirements
  const routeConfig = routePermissions.find((config) => config.path === route);
  if (!routeConfig) return true;

  // Check if user has required scopes
  return routeConfig.requiredScopes.every((scope) =>
    user.oauth_scopes.includes(scope),
  );
}

router.beforeEach(async (to, _from, next) => {
  const heartbeat = storeHeartbeat();
  const auth = storeAuth();
  const { user } = storeToRefs(auth);
  const currentRoute = to.name?.toString();

  try {
    // Handle setup wizard
    if (heartbeat.value.SYSTEM.SHOW_SETUP_WIZARD) {
      return currentRoute !== "setup" ? next({ name: ROUTES.SETUP }) : next();
    }

    // Handle authentication
    if (
      !user.value &&
      currentRoute !== ROUTES.LOGIN &&
      currentRoute !== ROUTES.RESET_PASSWORD &&
      currentRoute !== ROUTES.REGISTER
    ) {
      return next({
        name: ROUTES.LOGIN,
        query: {
          next: to.query.next ?? (to.path !== "/login" ? to.path : "/"),
        },
      });
    }

    if (user.value && currentRoute == ROUTES.SETUP) {
      return next({ name: ROUTES.HOME });
    }

    // Check permissions
    if (currentRoute && !checkRoutePermissions(currentRoute, user.value)) {
      return next({ name: ROUTES.NOT_FOUND });
    }

    if (to.meta.title) {
      document.title = i18n.global.t(to.meta.title as string);
    } else {
      document.title = "RomM";
    }
    next();
  } catch (error) {
    console.error("Navigation guard error:", error);
    document.title = "RomM";
    next({ name: ROUTES.LOGIN });
  }
});

router.beforeResolve(async () => {
  const viewTransition = startViewTransition();
  await viewTransition.captured;
});

export default router;
