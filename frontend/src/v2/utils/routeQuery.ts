// Batched query-param writes for URL-backed view state (search, view mode,
// toolbar filters).
//
// `router.replace` is async: `route.query` keeps returning the old value
// until the navigation resolves. Two controls changing in the same flush
// therefore both read the same stale snapshot, and the second `replace`
// wins with a query that never saw the first one's key, silently resetting
// it. Routing every writer through here merges the patches and issues one
// navigation per tick instead.
//
// A replace mid-navigation cancels it, or on Back/Forward overwrites the entry
// the browser moved to, so writes wait it out and drop if it left their page.
import { nextTick } from "vue";
import {
  isNavigationFailure,
  type LocationQuery,
  NavigationFailureType,
  type Router,
} from "vue-router";

/** The slice of vue-router's `Router` this needs. A real Router satisfies
 *  it structurally; narrowing it keeps the util testable without a stub
 *  that has to impersonate the whole router. */
export interface QueryRouter {
  readonly currentRoute: { value: { path: string; query: LocationQuery } };
  replace(to: { path: string; query: LocationQuery }): unknown;
}

type QueryPatch = Record<string, string | undefined>;

interface PendingWrite {
  path: string;
  patch: QueryPatch;
}

interface InFlightNavigation {
  to: unknown;
  waiters: (() => void)[];
}

// Keyed by router so two router instances (tests, nested apps) never share
// state.
const pendingByRouter = new WeakMap<QueryRouter, PendingWrite>();
const inFlightByRouter = new WeakMap<QueryRouter, InFlightNavigation>();

/** Track the router's in-flight navigation so query writes wait it out.
 *  Returns the remove function. */
export function installQueryNavigationGuard(router: Router): () => void {
  function settle() {
    const inFlight = inFlightByRouter.get(router);
    if (!inFlight) return;
    inFlightByRouter.delete(router);
    inFlight.waiters.forEach((run) => run());
  }

  const removeBeforeEach = router.beforeEach((to) => {
    const waiters = inFlightByRouter.get(router)?.waiters ?? [];
    inFlightByRouter.set(router, { to, waiters });
  });
  // Cancelled ones end after their successor started. Anything else settles,
  // including a redirect onto this page, a duplicate that skips `beforeEach`.
  const removeAfterEach = router.afterEach((_to, _from, failure) => {
    if (!isNavigationFailure(failure, NavigationFailureType.cancelled)) {
      settle();
    }
  });
  // A guard that throws skips `afterEach`.
  const removeOnError = router.onError((_error, to) => {
    if (inFlightByRouter.get(router)?.to === to) settle();
  });

  return () => {
    removeBeforeEach();
    removeAfterEach();
    removeOnError();
    inFlightByRouter.delete(router);
  };
}

function flush(router: QueryRouter): void {
  const write = pendingByRouter.get(router);
  if (!write) return;

  const inFlight = inFlightByRouter.get(router);
  if (inFlight) {
    inFlight.waiters.push(() => flush(router));
    return;
  }

  pendingByRouter.delete(router);
  const current = router.currentRoute.value;
  if (current.path !== write.path) return;

  const query: LocationQuery = { ...current.query };
  for (const [key, value] of Object.entries(write.patch)) {
    if (value === undefined) delete query[key];
    else query[key] = value;
  }
  void router.replace({ path: write.path, query });
}

/** Merge `patch` into the current query; `undefined` drops the param. */
export function patchQuery(router: QueryRouter, patch: QueryPatch): void {
  const path = router.currentRoute.value.path;
  const pending = pendingByRouter.get(router);
  // A write left over from a page the route has since moved off is stale.
  const merged = pending && pending.path === path ? pending.patch : {};
  pendingByRouter.set(router, { path, patch: { ...merged, ...patch } });

  void nextTick(() => flush(router));
}

/** Write one URL-backed value, `undefined` dropping the param. The compare
 *  against the live query is what stops a loop with the watcher reading it. */
export function syncQueryParam(
  router: QueryRouter,
  key: string,
  value: string | undefined,
): void {
  const raw = router.currentRoute.value.query[key];
  const current = typeof raw === "string" ? raw : undefined;
  if (value === current) return;
  patchQuery(router, { [key]: value });
}
