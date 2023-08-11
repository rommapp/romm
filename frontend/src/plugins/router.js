// Composables
import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/login",
    component: () => import("@/views/Login.vue"),
  },
  {
    path: "/",
    component: () => import("@/views/Home.vue"),
  },
  {
    path: "/platform/:platform",
    component: () => import("@/views/Gallery.vue"),
  },
  {
    path: "/platform/:platform/:rom",
    component: () => import("@/views/Details.vue"),
  },
  {
    path: "/library/scan",
    component: () => import("@/views/library/Scan.vue"),
  },
  {
    path: "/settings/control-panel",
    component: () => import("@/views/settings/ControlPanel.vue"),
  },
  {
    path: "/:pathMatch(.*)*",
    component: () => import("@/views/Home.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

export default router;
