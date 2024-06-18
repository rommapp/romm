// Composables
import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/Login.vue"),
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
        component: () => import("@/views/Gallery.vue"),
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
        path: "/library/scan",
        name: "libraryScan",
        component: () => import("@/views/Library/Scan.vue"),
      },
      {
        path: "/library/configuration",
        name: "libraryConfig",
        component: () => import("@/views/Library/Config.vue"),
      },
      {
        path: "/settings/general",
        name: "settingsGeneral",
        component: () => import("@/views/Settings/General.vue"),
      },
      {
        path: "/settings/users",
        name: "settingsUsers",
        component: () => import("@/views/Settings/Users.vue"),
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

router.afterEach(() => {
  // Scroll to top to avoid annoying behaviour in mobile
  window.scrollTo({ top: 0, left: 0 });
});

export default router;
