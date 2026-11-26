import { createMemoryHistory, createRouter } from "vue-router";

/** A bare in-memory router, for mounts whose components read the route or render a router link. */
export function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:rest(.*)*", component: { template: "<div />" } }],
  });
}
