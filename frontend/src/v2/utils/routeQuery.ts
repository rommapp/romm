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
import {
  isNavigationFailure,
  type LocationQuery,
  NavigationFailureType,
  type RouteLocation,
  type RouteLocationNormalized,
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
  /** Build on an empty query instead of the current one. */
  replace: boolean;
}

// Keyed by router so two router instances (tests, nested apps) never share
// state. The in-flight value is the target of the navigation under way.
const pendingByRouter = new WeakMap<QueryRouter, PendingWrite>();
const inFlightByRouter = new WeakMap<QueryRouter, RouteLocationNormalized>();

// Every hop of a guard redirect chain points back at the navigation it began as.
function originOf(to: RouteLocationNormalized): RouteLocation {
  return to.redirectedFrom ?? to;
}

/** Track the router's in-flight navigation so query writes wait it out.
 *  Returns the remove function. */
export function installQueryNavigationGuard(router: Router): () => void {
  function settle() {
    if (inFlightByRouter.delete(router)) flush(router);
  }

  const removeBeforeEach = router.beforeEach((to) => {
    inFlightByRouter.set(router, to);
  });
  // Only the tracked navigation settles, since an older one can end after its
  // successor started. A guard redirect onto this page ends as a duplicate.
  const removeAfterEach = router.afterEach((to, _from, failure) => {
    const tracked = inFlightByRouter.get(router);
    if (!tracked) return;
    if (
      tracked === to ||
      (isNavigationFailure(failure, NavigationFailureType.duplicated) &&
        originOf(to) === originOf(tracked))
    ) {
      settle();
    }
  });
  // A guard that throws skips `afterEach`.
  const removeOnError = router.onError((_error, to) => {
    if (inFlightByRouter.get(router) === to) settle();
  });

  return () => {
    removeBeforeEach();
    removeAfterEach();
    removeOnError();
    settle();
  };
}

// A write held back by a navigation is flushed again when it settles.
function flush(router: QueryRouter): void {
  const write = pendingByRouter.get(router);
  if (!write || inFlightByRouter.has(router)) return;

  pendingByRouter.delete(router);
  const current = router.currentRoute.value;
  if (current.path !== write.path) return;

  const query: LocationQuery = write.replace ? {} : { ...current.query };
  for (const [key, value] of Object.entries(write.patch)) {
    if (value === undefined) delete query[key];
    else query[key] = value;
  }
  void router.replace({ path: write.path, query });
}

function queueWrite(router: QueryRouter, patch: QueryPatch, replace: boolean) {
  const path = router.currentRoute.value.path;
  const pending = pendingByRouter.get(router);
  // A write left over from a page the route has since moved off is stale.
  const base = pending && pending.path === path && !replace ? pending : null;
  pendingByRouter.set(router, {
    path,
    patch: { ...base?.patch, ...patch },
    replace: replace || (base?.replace ?? false),
  });
  if (!pending) void nextTick(() => flush(router));
}

/** Merge `patch` into the current query; `undefined` drops the param. */
export function patchQuery(router: QueryRouter, patch: QueryPatch): void {
  queueWrite(router, patch, false);
}

/** Replace the whole query, dropping every param `query` doesn't name. */
export function replaceQuery(
  router: QueryRouter,
  query: Record<string, string>,
): void {
  queueWrite(router, query, true);
}

/** Write one URL-backed value, `undefined` dropping the param. The compare
 *  against the upcoming value is what stops a loop with the watcher reading it. */
export function syncQueryParam(
  router: QueryRouter,
  key: string,
  value: string | undefined,
): void {
  if (value === upcomingValue(router, key)) return;
  patchQuery(router, { [key]: value });
}

// What `key` will hold once the queued write lands, so a control switched
// back before then still gets written.
function upcomingValue(router: QueryRouter, key: string): string | undefined {
  const current = router.currentRoute.value;
  const pending = pendingByRouter.get(router);
  if (pending && pending.path === current.path) {
    if (key in pending.patch) return pending.patch[key];
    if (pending.replace) return undefined;
  }
  const raw = current.query[key];
  return typeof raw === "string" ? raw : undefined;
}
