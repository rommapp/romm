// Composables
import { createRouter, createWebHistory } from "vue-router";
import storeHeartbeat from "@/stores/heartbeat";
import storeAuth from "@/stores/auth";
import { storeToRefs } from "pinia";

const routes = [
  {
    path: "/setup",
    name: "setupView",
    component: () => import("@/layouts/Auth.vue"),
    children: [
      {
        path: "",
        name: "setup",
        component: () => import("@/views/Auth/Setup.vue"),
      },
    ],
  },
  {
    path: "/login",
    name: "loginView",
    component: () => import("@/layouts/Auth.vue"),
    children: [
      {
        path: "",
        name: "login",
        component: () => import("@/views/Auth/Login.vue"),
      },
    ],
  },
  {
    path: "/",
    name: "main",
    component: () => import("@/layouts/Main.vue"),
    children: [
      {
        path: "",
        name: "home",
        component: () => import("@/views/Home.vue"),
      },
      {
        path: "search",
        name: "search",
        component: () => import("@/views/Gallery/Search.vue"),
      },
      {
        path: "platform/:platform",
        name: "platform",
        component: () => import("@/views/Gallery/Platform.vue"),
      },
      {
        path: "collection/:collection",
        name: "collection",
        component: () => import("@/views/Gallery/Collection.vue"),
      },
      {
        path: "rom/:rom",
        name: "rom",
        component: () => import("@/views/GameDetails.vue"),
      },
      {
        path: "rom/:rom/ejs",
        name: "emulatorjs",
        component: () => import("@/views/Player/EmulatorJS/Base.vue"),
      },
      {
        path: "rom/:rom/ruffle",
        name: "ruffle",
        component: () => import("@/views/Player/RuffleRS/Base.vue"),
      },
      {
        path: "scan",
        name: "scan",
        component: () => import("@/views/Scan.vue"),
      },
      {
        path: "user-interface",
        component: () => import("@/layouts/Settings.vue"),
        children: [
          {
            path: "",
            name: "userInterface",
            component: () => import("@/views/Settings/UserInterface.vue"),
          },
        ],
      },
      {
        path: "library-management",
        component: () => import("@/layouts/Settings.vue"),
        children: [
          {
            path: "",
            name: "libraryManagement",
            component: () => import("@/views/Settings/LibraryManagement.vue"),
          },
        ],
      },
      {
        path: "administration",
        component: () => import("@/layouts/Settings.vue"),
        children: [
          {
            path: "",
            name: "administration",
            component: () => import("@/views/Settings/Administration.vue"),
          },
        ],
      },
      {
        path: ":pathMatch(.*)*",
        name: "404",
        component: () => import("@/views/404.vue"),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

router.beforeEach(async (to, _from, next) => {
  const heartbeat = storeHeartbeat();
  const auth = storeAuth();
  const { user } = storeToRefs(auth);

  if (
    heartbeat.value.SYSTEM.SHOW_SETUP_WIZARD &&
    to.name?.toString() !== "setup"
  ) {
    next({ name: "setup" });
  } else if (!heartbeat.value.SYSTEM.SHOW_SETUP_WIZARD) {
    if (
      (to.name?.toString() === "login" || to.name?.toString() === "setup") &&
      user.value
    ) {
      next({ name: "home" });
    } else if (to.name?.toString() !== "login" && !user.value) {
      next({ name: "login" });
    } else if (
      to.name &&
      user.value &&
      ((["scan", "management"].includes(to.name.toString()) &&
        !user.value.oauth_scopes.includes("platforms.write")) ||
        (["administration"].includes(to.name.toString()) &&
          !user.value.oauth_scopes.includes("users.write")))
    ) {
      next({ name: "404" });
    } else {
      next();
    }
  } else {
    next();
  }
});

router.afterEach(() => {
  // Scroll to top to avoid annoying behaviour on mobile
  window.scrollTo({ top: 0, left: 0 });
});

export default router;
