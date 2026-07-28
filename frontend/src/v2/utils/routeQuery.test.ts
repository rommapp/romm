import { describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { LocationQuery } from "vue-router";
import { patchQuery, type QueryRouter } from "./routeQuery";

// Minimal router stub reproducing the trait that causes the bug: `replace`
// is async, so `currentRoute.query` still reads the pre-navigation value
// for anything running in the same flush.
function fakeRouter(initial: LocationQuery = {}) {
  const currentRoute = ref({ query: { ...initial } });
  const replace = vi.fn(async ({ query }: { query: LocationQuery }) => {
    await Promise.resolve();
    currentRoute.value = { query: { ...query } };
  });
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
      query: { kind: "virtual" },
    });
  });

  it("drops a param when the patch value is undefined", async () => {
    const router = fakeRouter({ search: "zelda", show: "all" });

    patchQuery(router, { search: undefined });
    await nextTick();

    expect(router.replace).toHaveBeenCalledWith({ query: { show: "all" } });
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
      query: { show: "all", search: "zelda" },
    });
  });
});
