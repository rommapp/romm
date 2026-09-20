import { createPinia, setActivePinia } from "pinia";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import type { RouteLocationNormalized } from "vue-router";
import i18n, { localesReady } from "@/locales";
import router, { applyRouteTitle } from "@/plugins/router";

describe("route titles", () => {
  beforeAll(async () => {
    setActivePinia(createPinia());
    await localesReady;
  });

  it("stores i18n keys that resolve against the locale messages", () => {
    const titles = router
      .getRoutes()
      .map((route) => route.meta.title)
      .filter((title): title is string => typeof title === "string");

    expect(titles.length).toBeGreaterThan(0);

    for (const title of titles) {
      // Route definitions must hold the key, not an eagerly translated
      // string: messages load after the route table is built.
      expect(title).toMatch(/^[a-z0-9-]+\.[a-z0-9-]+$/);
      expect(i18n.global.t(title)).not.toBe(title);
    }
  });
});

describe("applyRouteTitle", () => {
  const routeAt = (path: string, meta: Record<string, unknown> = {}) =>
    ({ path, meta }) as unknown as RouteLocationNormalized;

  beforeAll(async () => {
    await localesReady;
  });

  beforeEach(() => {
    document.title = "";
  });

  it("translates the route's i18n key", () => {
    applyRouteTitle(routeAt("/", { title: "settings.home" }));
    expect(document.title).toBe(i18n.global.t("settings.home"));
  });

  it("falls back to RomM on a route that owns no title", () => {
    applyRouteTitle(routeAt("/rom/1"), routeAt("/"));
    expect(document.title).toBe("RomM");
  });

  it("keeps the view's title across a query-only navigation", () => {
    document.title = "Chrono Trigger";
    applyRouteTitle(routeAt("/rom/1"), routeAt("/rom/1"));
    expect(document.title).toBe("Chrono Trigger");
  });

  it("still applies a route title on a query-only navigation", () => {
    document.title = "stale";
    applyRouteTitle(routeAt("/", { title: "settings.home" }), routeAt("/"));
    expect(document.title).toBe(i18n.global.t("settings.home"));
  });
});
