import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import {
  createMemoryHistory,
  createRouter,
  type LocationQuery,
  type Router,
} from "vue-router";
import {
  installQueryNavigationGuard,
  patchQuery,
  type QueryRouter,
  replaceQuery,
  syncQueryParam,
} from "./routeQuery";

// Minimal router stub reproducing the trait that causes the bug: `replace`
// is async, so `currentRoute.query` still reads the pre-navigation value
// for anything running in the same flush.
function fakeRouter(initial: LocationQuery = {}) {
  const currentRoute = ref({ path: "/", query: { ...initial } });
  const replace = vi.fn(
    async ({ path, query }: { path: string; query: LocationQuery }) => {
      await Promise.resolve();
      currentRoute.value = { path, query: { ...query } };
    },
  );
  const router: QueryRouter & { replace: typeof replace } = {
    currentRoute,
    replace,
  };
  return router;
}

describe("patchQuery", () => {
  it("merges same-tick writes into one navigation", async () => {
    const router = fakeRouter({ search: "zelda" });

    patchQuery(router, { show: "all" });
    patchQuery(router, { layout: "list" });
    await nextTick();

    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith({
      path: "/",
      query: { search: "zelda", show: "all", layout: "list" },
    });
  });

  it("keeps a param a later same-tick write didn't touch", async () => {
    const router = fakeRouter({ vis: "private" });

    // The exact shape of the reported bug: one control sets a param while
    // another clears a different one in the same flush.
    patchQuery(router, { kind: "virtual" });
    patchQuery(router, { vis: undefined });
    await nextTick();

    expect(router.replace).toHaveBeenCalledWith({
      path: "/",
      query: { kind: "virtual" },
    });
  });

  it("drops a param when the patch value is undefined", async () => {
    const router = fakeRouter({ search: "zelda", show: "all" });

    patchQuery(router, { search: undefined });
    await nextTick();

    expect(router.replace).toHaveBeenCalledWith({
      path: "/",
      query: { show: "all" },
    });
  });

  it("builds later ticks off the navigated query", async () => {
    const router = fakeRouter();

    patchQuery(router, { show: "all" });
    await nextTick();
    await Promise.resolve();

    patchQuery(router, { search: "zelda" });
    await nextTick();

    expect(router.replace).toHaveBeenCalledTimes(2);
    expect(router.replace).toHaveBeenLastCalledWith({
      path: "/",
      query: { show: "all", search: "zelda" },
    });
  });
});

describe("syncQueryParam", () => {
  it("writes a value switched back before the queued write lands", async () => {
    const router = fakeRouter();

    syncQueryParam(router, "tab", "send");
    syncQueryParam(router, "tab", undefined);
    await nextTick();

    expect(router.replace).toHaveBeenCalledWith({ path: "/", query: {} });
  });

  it("skips a value the URL already holds", async () => {
    const router = fakeRouter({ tab: "send" });

    syncQueryParam(router, "tab", "send");
    await nextTick();

    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("replaceQuery", () => {
  it("drops every param the new query doesn't name", async () => {
    const router = fakeRouter({ q: "steam", category: "security" });

    replaceQuery(router, { tab: "logs" });
    await nextTick();

    expect(router.replace).toHaveBeenCalledWith({
      path: "/",
      query: { tab: "logs" },
    });
  });

  it("keeps a same-tick patch made after it", async () => {
    const router = fakeRouter({ q: "steam" });

    replaceQuery(router, {});
    patchQuery(router, { tab: "events" });
    await nextTick();

    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith({
      path: "/",
      query: { tab: "events" },
    });
  });
});

describe("patchQuery during a navigation", () => {
  let router: Router;
  let removeGuard: () => void;
  // While set, navigations wait in `beforeResolve` for `release()`, the way
  // the view-transition and data-fetch guards hold them in the app.
  let holding = false;
  let held: (() => void) | undefined;

  function release() {
    const resume = held;
    held = undefined;
    resume?.();
  }

  /** Start holding, then wait until `start()`'s navigation is held. */
  async function hold(start: () => unknown) {
    holding = true;
    start();
    await vi.waitFor(() => expect(held).toBeDefined());
    holding = false;
  }

  async function setup() {
    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: "/:page", component: { render: () => null } }],
    });
    router.beforeResolve(async () => {
      if (!holding) return;
      await new Promise<void>((resolve) => (held = resolve));
    });
    removeGuard = installQueryNavigationGuard(router);
    await router.push("/a");
    await router.push("/b");
  }

  afterEach(() => removeGuard?.());

  it("lets a pending push land and drops the write for the page it left", async () => {
    await setup();

    await hold(() => router.push("/c"));
    patchQuery(router, { tab: "files" });
    await nextTick();
    release();
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/c"));
    await nextTick();

    expect(router.currentRoute.value.fullPath).toBe("/c");
    expect(router.options.history.location).toBe("/c");
  });

  it("keeps the entry a pending Back navigation moved to", async () => {
    await setup();

    await hold(() => router.back());
    patchQuery(router, { search: "x" });
    await nextTick();
    release();
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/a"));
    await nextTick();

    expect(router.currentRoute.value.fullPath).toBe("/a");
    expect(router.options.history.location).toBe("/a");
  });

  it("applies a write once a same-page navigation settles", async () => {
    await setup();

    await hold(() => router.replace({ path: "/b", query: { show: "all" } }));
    patchQuery(router, { search: "zelda" });
    await nextTick();
    release();

    await vi.waitFor(() =>
      expect(router.currentRoute.value.fullPath).toBe(
        "/b?show=all&search=zelda",
      ),
    );
  });

  it("applies a write once a redirect lands back on the current page", async () => {
    await setup();
    const removeRedirect = router.beforeEach((to) =>
      to.path === "/forbidden" ? "/b" : undefined,
    );

    await router.push("/forbidden");
    removeRedirect();
    patchQuery(router, { search: "zelda" });

    await vi.waitFor(() =>
      expect(router.currentRoute.value.fullPath).toBe("/b?search=zelda"),
    );
  });

  it("applies a held write when the guard is removed", async () => {
    await setup();

    await hold(() => router.replace({ path: "/b", query: { show: "all" } }));
    patchQuery(router, { search: "zelda" });
    await nextTick();
    removeGuard();
    release();

    await vi.waitFor(() =>
      expect(router.currentRoute.value.query).toMatchObject({
        search: "zelda",
      }),
    );
  });

  it("keeps waiting when an older navigation aborts after a newer one started", async () => {
    await setup();
    let abort: (() => void) | undefined;
    const removeAborting = router.beforeEach(
      (to) =>
        new Promise<boolean | void>((resolve) => {
          if (to.path !== "/slow") return resolve();
          abort = () => resolve(false);
        }),
    );

    let aborted = false;
    const removeWatch = router.afterEach((to) => {
      if (to.path === "/slow") aborted = true;
    });

    void router.push("/slow");
    await vi.waitFor(() => expect(abort).toBeDefined());
    await hold(() => router.push("/c"));
    abort?.();
    await vi.waitFor(() => expect(aborted).toBe(true));
    removeAborting();
    removeWatch();
    patchQuery(router, { tab: "files" });
    await nextTick();
    release();

    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe("/c"));
    await nextTick();
    expect(router.currentRoute.value.fullPath).toBe("/c");
  });

  it("applies a write once a failed navigation settles", async () => {
    await setup();
    router.onError(() => {});
    let fail: (() => void) | undefined;
    const removeFailing = router.beforeEach(
      (to) =>
        new Promise<void>((resolve, reject) => {
          if (to.path !== "/boom") return resolve();
          fail = () => reject(new Error("guard failed"));
        }),
    );

    void router.push("/boom").catch(() => {});
    await vi.waitFor(() => expect(fail).toBeDefined());
    patchQuery(router, { search: "zelda" });
    await nextTick();
    expect(router.currentRoute.value.fullPath).toBe("/b");
    fail?.();
    removeFailing();

    await vi.waitFor(() =>
      expect(router.currentRoute.value.fullPath).toBe("/b?search=zelda"),
    );
  });
});
