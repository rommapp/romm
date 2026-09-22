import { createPinia, setActivePinia } from "pinia";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import type { RouteLocationNormalized } from "vue-router";
import i18n, { localesReady } from "@/locales";
import router, { applyRouteTitle, ROUTES } from "@/plugins/router";
import storeAuth from "@/stores/auth";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { User } from "@/stores/users";

const { getRom, stubView } = vi.hoisted(() => ({
  getRom: vi.fn(),
  stubView: () => ({ default: { render: () => null } }),
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom },
}));

// Navigating resolves the route's lazy views, which import most of the app and
// outlast the test timeout when the whole suite transforms in parallel.
vi.mock("@/layouts/Main.vue", stubView);
vi.mock("@/views/GameDetails.vue", stubView);
vi.mock("@/v2/layouts/AppLayout.vue", stubView);
vi.mock("@/v2/views/GameDetails.vue", stubView);

function makeRom(overrides: Partial<DetailedRom> = {}): DetailedRom {
  return {
    id: 1,
    name: "Chrono Trigger",
    ...overrides,
  } as unknown as DetailedRom;
}

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
  const routeAt = (
    path: string,
    meta: RouteLocationNormalized["meta"] = {},
  ): RouteLocationNormalized => {
    const resolved = router.resolve(path);
    return { ...resolved, name: resolved.name ?? undefined, meta };
  };

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

describe("the rom route", () => {
  beforeAll(async () => {
    setActivePinia(createPinia());
    await localesReady;
  });

  // A play page writes saves server-side and then navigates here, so an id
  // matching the route is not proof the store's copy is current.
  it("re-reads a rom the store already holds", async () => {
    const roms = storeRoms();
    storeAuth().setCurrentUser({ id: 1 } as User);
    roms.setCurrentRom(makeRom({ id: 9, name: "before the session" }));
    getRom.mockResolvedValue({
      data: makeRom({ id: 9, name: "after the session" }),
    });

    await router.push({ name: ROUTES.ROM, params: { rom: 9 } });

    expect(getRom).toHaveBeenCalledWith({ romId: 9 });
    expect(roms.currentRom?.name).toBe("after the session");
  });
});
