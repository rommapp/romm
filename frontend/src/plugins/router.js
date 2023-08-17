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
        path: "/platform/:platform/:rom",
        name: "rom",
        component: () => import("@/views/Details/Base.vue"),
      },
      {
        path: "/library/scan",
        name: "scan",
        component: () => import("@/views/Library/Scan.vue"),
      },
      {
        path: "/settings/control-panel",
        name: "controlPanel",
        component: () => import("@/views/Settings/ControlPanel.vue"),
      },
      {
        path: "/:pathMatch(.*)*",
        name: "noMatch",
        component: () => import("@/views/Dashboard/Base.vue"),
      },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes,
});

function isAuthenticated() {
  return localStorage.getItem("authenticated") === "true";
}

router.beforeEach(async (to, from) => {
  const publicPages = ["/login"];
  const authRequired = !publicPages.includes(to.path);

  if (!isAuthenticated() && to.name !== "login" && authRequired) {
    return { name: "login" };
  } else if (isAuthenticated() && to.name === "login") {
    return { name: "dashboard" };
  } else if (to.name == "noMatch") {
    return { name: "dashboard" };
  }
});

export default router;
