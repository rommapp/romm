// Composables
import { createRouter, createWebHistory } from "vue-router";
import storeHeartbeat from "@/stores/heartbeat";

const routes = [
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/Login.vue"),
  },
  {
    path: "/setup",
    name: "setup",
    component: () => import("@/views/Setup.vue"),
  },
  {
    path: "/",
    name: "home",
    component: () => import("@/views/Home.vue"),
    children: [
      {
        path: "/",
        name: "dashboard",
        component: () => import("@/views/Dashboard.vue"),
      },
      {
        path: "/platform/:platform",
        name: "platform",
        component: () => import("@/views/Gallery/Platform.vue"),
      },
      {
        path: "/collection/:collection",
        name: "collection",
        component: () => import("@/views/Gallery/Collection.vue"),
      },
      {
        path: "/rom/:rom",
        name: "rom",
        component: () => import("@/views/GameDetails.vue"),
      },
      {
        path: "/rom/:rom/ejs",
        name: "emulatorjs",
        component: () => import("@/views/EmulatorJS/Base.vue"),
      },
      {
        path: "/rom/:rom/ruffle",
        name: "ruffle",
        component: () => import("@/views/RuffleRS/Base.vue"),
      },
      {
        path: "/scan",
        name: "scan",
        component: () => import("@/views/Scan.vue"),
      },
      {
        path: "/management",
        name: "management",
        component: () => import("@/views/Management.vue"),
      },
      {
        path: "/settings",
        name: "settings",
        component: () => import("@/views/Settings.vue"),
      },
      {
        path: "/administration",
        name: "administration",
        component: () => import("@/views/Administration.vue"),
      },
      {
        path: "/:pathMatch(.*)*",
        name: "noMatch",
        component: () => import("@/views/Dashboard.vue"),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

router.beforeEach((to, _from, next) => {
  const heartbeat = storeHeartbeat();
  if (to.name == "setup" && !heartbeat.value.SHOW_SETUP_WIZARD) {
    next({ name: "dashboard" });
  } else {
    next();
  }
});

router.afterEach(() => {
  // Scroll to top to avoid annoying behaviour in mobile
  window.scrollTo({ top: 0, left: 0 });
});

export default router;
