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
        component: () => import("@/views/Dashboard/Base.vue"),
      },
      {
        path: "/platform/:platform",
        name: "platform",
        component: () => import("@/views/Gallery/Base.vue"),
      },
      {
        path: "/rom/:rom",
        name: "rom",
        component: () => import("@/views/Details/Base.vue"),
      },
      {
        path: "/library/scan",
        name: "scan",
        component: () => import("@/views/Library/Scan/Base.vue"),
      },
      {
        path: "/settings/control-panel/",
        name: "controlPanel",
        component: () => import("@/views/Settings/ControlPanel/Base.vue"),
      },
      {
        path: "/:pathMatch(.*)*",
        name: "noMatch",
        component: () => import("@/views/Dashboard/Base.vue"),
      },
    ],
  },
  {
    path: "/play/:rom",
    component: () => import("@/views/Play/Base.vue"),
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
