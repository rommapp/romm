// Batched query-param writes for URL-backed view state (search, view mode,
// toolbar filters).
//
// `router.replace` is async: `route.query` keeps returning the old value
// until the navigation resolves. Two controls changing in the same flush
// therefore both read the same stale snapshot, and the second `replace`
// wins with a query that never saw the first one's key, silently resetting
// it. Routing every writer through here merges the patches and issues one
// navigation per tick instead.
import { nextTick } from "vue";
import type { LocationQuery } from "vue-router";

/** The slice of vue-router's `Router` this needs. A real Router satisfies
 *  it structurally; narrowing it keeps the util testable without a stub
 *  that has to impersonate the whole router. */
export interface QueryRouter {
  readonly currentRoute: { value: { query: LocationQuery } };
  replace(to: { query: LocationQuery }): unknown;
}

// Pending merge for the current tick, keyed by router so two router
// instances (tests, nested apps) never share a buffer.
const pendingByRouter = new WeakMap<QueryRouter, LocationQuery>();

/** Merge `patch` into the current query; `undefined` drops the param. */
export function patchQuery(
  router: QueryRouter,
  patch: Record<string, string | undefined>,
): void {
  const merged: LocationQuery = pendingByRouter.get(router) ?? {
    ...router.currentRoute.value.query,
  };

  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined) delete merged[key];
    else merged[key] = value;
  }

  pendingByRouter.set(router, merged);

  void nextTick(() => {
    const query = pendingByRouter.get(router);
    if (!query) return;
    pendingByRouter.delete(router);
    void router.replace({ query });
  });
}
