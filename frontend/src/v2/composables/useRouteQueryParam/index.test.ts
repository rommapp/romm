import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { defineComponent } from "vue";
import {
  createMemoryHistory,
  createRouter,
  type LocationQueryRaw,
} from "vue-router";
import { useRouteQueryParam } from "./index";

const TABS = ["library", "settings"] as const;

async function mountAt(query: LocationQueryRaw) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/platform/:id", component: { template: "<div />" } }],
  });
  await router.push({ path: "/platform/1", query });

  const Host = defineComponent({
    setup() {
      return {
        tab: useRouteQueryParam("tab", "library", TABS),
        search: useRouteQueryParam("search"),
      };
    },
    render: () => null,
  });
  const { vm } = mount(Host, { global: { plugins: [router] } });
  return { router, vm };
}

describe("useRouteQueryParam", () => {
  it("reads the param from the URL", async () => {
    const { vm } = await mountAt({ tab: "settings", search: "zelda" });

    expect(vm.tab).toBe("settings");
    expect(vm.search).toBe("zelda");
  });

  it("falls back on a missing or unknown value", async () => {
    const { vm } = await mountAt({ tab: "bogus" });

    expect(vm.tab).toBe("library");
    expect(vm.search).toBe("");
  });

  it("writes a change back to the URL", async () => {
    const { router, vm } = await mountAt({});

    vm.tab = "settings";
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({ tab: "settings" });
  });

  it("drops the param when set back to the fallback", async () => {
    const { router, vm } = await mountAt({ tab: "settings", search: "zelda" });

    vm.tab = "library";
    vm.search = "";
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({});
  });

  it("lands two params changed in the same tick", async () => {
    const { router, vm } = await mountAt({});

    vm.tab = "settings";
    vm.search = "zelda";
    await flushPromises();

    expect(router.currentRoute.value.query).toEqual({
      tab: "settings",
      search: "zelda",
    });
  });

  it("follows an external navigation", async () => {
    const { router, vm } = await mountAt({ tab: "settings" });

    await router.push({ path: "/platform/1", query: { search: "mario" } });
    await flushPromises();

    expect(vm.tab).toBe("library");
    expect(vm.search).toBe("mario");
  });
});
