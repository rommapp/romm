// Composables
import { createRouter, createWebHistory } from "vue-router";
import storeHeartbeat from "@/stores/heartbeat";
import storeAuth from "@/stores/auth";
import { storeToRefs } from "pinia";

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
        path: "/rom/:rom/play",
        name: "play",
        component: () => import("@/views/Play/Base.vue"),
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

router.beforeEach((to, from) => {
  const heartbeat = storeHeartbeat();
  if (to.name == "setup" && !heartbeat.value.SETUP_WIZARD) {
    router.push({ name: "dashboard" });
  }
});

router.afterEach((to, from) => {
  const auth = storeAuth();
  const { user } = storeToRefs(auth);
  if (
    to.name &&
    user.value &&
    ((["scan", "management"].includes(to.name.toString()) &&
      !user.value.oauth_scopes.includes("platforms.write")) ||
      (["administration"].includes(to.name.toString()) &&
        !user.value.oauth_scopes.includes("users.write")))
  ) {
    router.push(from);
  }
  // Scroll to top to avoid annoying behaviour in mobile
  window.scrollTo({ top: 0, left: 0 });
});

export default router;
