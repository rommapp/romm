import { flushPromises, mount } from "@vue/test-utils";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h } from "vue";
import { RouterView, type RouteLocationNormalized } from "vue-router";
import { useUiVersion } from "@/composables/useUiVersion";
import i18n, { localesReady } from "@/locales";
import router, { applyRouteTitle, ROUTES } from "@/plugins/router";
import storeAuth from "@/stores/auth";
import storeRoms, { type DetailedRom } from "@/stores/roms";
import type { User } from "@/stores/users";
import { makeDetailedRom } from "@/utils/rom.fixtures";

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
  return makeDetailedRom({ name: "Chrono Trigger", ...overrides });
}

describe("route titles", () => {
  beforeAll(async () => {
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
    expect(roms.getDetailedRom(9)?.name).toBe("after the session");
  });
});

describe("the inactive UI's views", () => {
  const uiVersion = useUiVersion();
  const v1View = { name: "V1View", render: () => h("p", "v1 view") };
  const loadV1 = vi.fn(async () => v1View);
  const loadV2 = vi.fn(async () => ({ render: () => null }));

  router.addRoute({
    path: "/deferred-views",
    name: "deferred-views",
    components: { default: loadV1, v2: loadV2 },
  });
  router.addRoute({
    path: "/deferred-views-elsewhere",
    name: "deferred-views-elsewhere",
    component: { render: () => null },
  });
  const loadLayoutV1 = vi.fn(async () => ({ render: () => h(RouterView) }));
  const loadChildV1 = vi.fn(async () => v1View);
  router.addRoute({
    path: "/deferred-chain",
    components: { default: loadLayoutV1, v2: { render: () => null } },
    children: [
      {
        path: "",
        name: "deferred-chain",
        components: { default: loadChildV1, v2: { render: () => null } },
      },
    ],
  });
  const views = () =>
    router.getRoutes().find((r) => r.name === "deferred-views")?.components;

  beforeEach(() => {
    storeAuth().setCurrentUser({ id: 1 } as User);
    uiVersion.value = "v2";
  });

  it("are left unfetched, without vue-router's async-view warning", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    await router.push({ name: "deferred-views" });

    expect(loadV2).toHaveBeenCalledOnce();
    expect(loadV1).not.toHaveBeenCalled();
    expect(views()?.default).toMatchObject({ name: "DeferredView" });
    expect(warn).not.toHaveBeenCalledWith(
      expect.stringContaining("defineAsyncComponent"),
    );
  });

  it("render in place when the UI switches without navigating", async () => {
    await router.push({ name: "deferred-views-elsewhere" });
    await router.push({ name: "deferred-views" });
    const Shell = defineComponent({
      render: () =>
        h(RouterView, { name: uiVersion.value === "v2" ? "v2" : "default" }),
    });
    const wrapper = mount(Shell, { global: { plugins: [router] } });

    uiVersion.value = "v1";
    await flushPromises();

    expect(wrapper.text()).toBe("v1 view");
  });

  it("start loading every nested view as soon as the UI switches", async () => {
    await router.push({ name: "deferred-chain" });

    uiVersion.value = "v1";
    await flushPromises();

    expect(loadLayoutV1).toHaveBeenCalledOnce();
    expect(loadChildV1).toHaveBeenCalledOnce();
  });

  // After an in-place switch, entering the route again must await the view
  // like any lazy route, so a stale chunk reaches router.onError.
  it("are fetched with the navigation once their UI is active", async () => {
    await router.push({ name: "deferred-views" });
    await router.push({ name: "deferred-views-elsewhere" });
    expect(views()?.default).toMatchObject({ name: "DeferredView" });
    uiVersion.value = "v1";

    await router.push({ name: "deferred-views" });

    expect(loadV1).toHaveBeenCalledOnce();
    expect(views()?.default).toBe(v1View);
  });
});

describe("removed console mode", () => {
  it("sends old /console links home", () => {
    const [match] = router.resolve("/console/rom/3/play").matched;

    expect(match?.redirect).toBe("/");
  });
});
